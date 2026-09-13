"""
Sanctions screening engine: an in-memory index over every name and alias in
the combined list, with entity-type filtering and DOB/nationality agreement.

Build once per loaded list (cached alongside SanctionsLoader's cache); screen
in a few milliseconds by scoring only candidates that share a blocking key.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Set

import pandas as pd
from rapidfuzz import fuzz

from ..core.countries_match import nationalities_to_iso2, nationality_agreement
from ..core.dates import dob_agreement, format_dates, parse_dob_text, parse_iso_date
from ..core.names import PARTICLES, blocking_keys, normalize, split_multi, tokens
from .sanctions_loader import SanctionsLoader

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 85
ENTITY_TYPES = {"person": {"individual"}, "entity": {"entity", "organization", "government"},
                "vessel": {"vessel"}, "any": None}


@dataclass
class Entry:
    idx: int
    source: str
    dataid: str
    record_type: str
    name: str
    aliases: List[str]
    variants: List[str]          # normalized name + aliases, deduplicated
    dob_dates: Set[date]
    dob_years: Set[int]
    nationalities: str
    nationality_codes: Set[str]
    program: str
    list_type: str
    listed_on: str
    id_numbers: str = ""
    keys: Set[str] = field(default_factory=set)


@dataclass
class Candidate:
    entry: Entry
    similarity: float
    matched_name: str
    match_type: str              # "name", "alias" or "identifier"
    dob_agreement: str           # exact | year | mismatch | unknown
    nationality_agreement: str   # match | mismatch | unknown
    name_similarity: Optional[float] = None  # identifier hits: how well the name agrees as well

    def to_dict(self) -> Dict:
        e = self.entry
        return {
            "sanctioned_name": e.name,
            "matched_name": self.matched_name,
            "match_type": self.match_type,
            "source": e.source,
            "dataid": e.dataid,
            "record_type": e.record_type,
            "program": e.program or e.list_type,
            "listed_on": e.listed_on,
            "id_numbers": e.id_numbers or None,
            "similarity": round(self.similarity, 2),
            "name_similarity": round(self.name_similarity, 2) if self.name_similarity is not None else None,
            "aliases": e.aliases[:10],
            "dob": format_dates(e.dob_dates, e.dob_years) or None,
            "dob_agreement": self.dob_agreement,
            "dob_match": {"exact": True, "year": True, "mismatch": False}.get(self.dob_agreement),
            "country": e.nationalities or None,
            "country_match": {"match": True, "mismatch": False}.get(self.nationality_agreement),
        }


class ScreeningIndex:
    def __init__(self, df: pd.DataFrame, list_version: str):
        t0 = time.time()
        self.list_version = list_version
        self.entries: List[Entry] = []
        self._by_key: Dict[str, Set[int]] = {}
        self._by_id: Dict[str, Set[int]] = {}   # normalized identity number -> entries
        for i, row in enumerate(df.itertuples(index=False)):
            r = row._asdict()
            name = str(r.get("name") or "")
            aliases = split_multi(r.get("aliases", ""))
            variants: List[str] = []
            seen: Set[str] = set()
            for v in [name] + aliases:
                n = normalize(v)
                if n and n not in seen:
                    seen.add(n)
                    variants.append(n)
            dates, years = parse_dob_text(str(r.get("dob_dates") or ""))
            _, yrs2 = parse_dob_text(str(r.get("dob_years") or ""))
            years |= yrs2
            nat = str(r.get("nationalities") or "")
            entry = Entry(
                idx=i, source=str(r.get("source") or ""), dataid=str(r.get("dataid") or ""),
                record_type=str(r.get("record_type") or "").lower(), name=name, aliases=aliases,
                variants=variants, dob_dates=dates, dob_years=years, nationalities=nat,
                nationality_codes=nationalities_to_iso2(nat), program=str(r.get("program") or ""),
                list_type=str(r.get("list_type") or ""), listed_on=str(r.get("listed_on") or ""),
                id_numbers=str(r.get("id_numbers") or ""),
            )
            for idn in identifier_keys(entry.id_numbers):
                self._by_id.setdefault(idn, set()).add(i)
            for v in variants:
                entry.keys |= blocking_keys(v)
            for k in entry.keys:
                self._by_key.setdefault(k, set()).add(i)
            self.entries.append(entry)
        self.built_in = time.time() - t0
        logger.info(f"Screening index built: {len(self.entries)} entries, {len(self._by_key)} keys, {self.built_in:.2f}s")

    # ------------------------------------------------------------------ #
    def by_identifier(self, id_numbers: List[str]) -> Set[int]:
        hits: Set[int] = set()
        for v in id_numbers or []:
            for k in identifier_keys(v):
                hits |= self._by_id.get(k, set())
        return hits

    def candidates(self, query: str) -> Set[int]:
        keys = blocking_keys(query)
        if not keys:
            return set()
        significant = [t for t in tokens(query) if t not in PARTICLES and len(t) >= 2]
        need = 1 if len(significant) <= 1 else min(2, math.ceil(len(significant) / 2))
        counts: Dict[int, int] = {}
        # Count distinct query tokens (not keys) matched per entry, so a token and
        # its skeleton do not double-count.
        for tok in significant:
            hit: Set[int] = set()
            for k in blocking_keys(tok):
                hit |= self._by_key.get(k, set())
            for i in hit:
                counts[i] = counts.get(i, 0) + 1
        return {i for i, c in counts.items() if c >= need}

    def screen(
        self,
        full_name: str,
        dob: Optional[str] = None,
        nationality: Optional[str] = None,
        entity_type: str = "person",
        threshold: int = SIMILARITY_THRESHOLD,
        limit: int = 25,
        id_numbers: Optional[List[str]] = None,
    ) -> List[Candidate]:
        q = normalize(full_name)
        allowed = ENTITY_TYPES.get(entity_type, ENTITY_TYPES["person"])
        query_dob = parse_iso_date(dob)
        results: List[Candidate] = []
        # Exact identity-number matches first: a QID or passport number on a list is a
        # definite hit regardless of how the name was spelled.
        # Some lists carry one number against several people (the Qatar NCTC record does), so
        # every identifier hit also records how well the name agrees and the best name ranks first.
        id_hits = self.by_identifier(id_numbers or [])
        for i in id_hits:
            e = self.entries[i]
            name_sim = max((fuzz.token_set_ratio(q, v) for v in e.variants), default=0.0) if q else None
            results.append(Candidate(
                entry=e, similarity=100.0, matched_name=e.id_numbers, match_type="identifier",
                dob_agreement=dob_agreement(query_dob, e.dob_dates, e.dob_years),
                nationality_agreement=nationality_agreement(nationality, e.nationality_codes),
                name_similarity=name_sim,
            ))
        if not q:
            return results[:limit]
        for i in self.candidates(full_name):
            if i in id_hits:
                continue
            e = self.entries[i]
            if allowed is not None and e.record_type not in allowed:
                continue
            best, best_variant = 0.0, ""
            for v in e.variants:
                s = fuzz.token_sort_ratio(q, v)
                if s > best:
                    best, best_variant = s, v
            if best < threshold:
                continue
            match_type = "name" if best_variant == e.variants[0] else "alias"
            matched = e.name if match_type == "name" else next(
                (a for a in e.aliases if normalize(a) == best_variant), best_variant)
            results.append(Candidate(
                entry=e, similarity=best, matched_name=matched, match_type=match_type,
                dob_agreement=dob_agreement(query_dob, e.dob_dates, e.dob_years),
                nationality_agreement=nationality_agreement(nationality, e.nationality_codes),
            ))
        results.sort(key=lambda c: (c.match_type != "identifier", -c.similarity, -(c.name_similarity or 0),
                                    c.dob_agreement != "exact", c.entry.name))
        return results[:limit]


def identifier_keys(value: str) -> Set[str]:
    """Normalized forms of the identity numbers in a list field such as
    'QID: 28560812345; Passport: A1234567' or a single customer-supplied number.
    Letters and digits only, uppercase; numbers shorter than 5 are ignored."""
    keys: Set[str] = set()
    for part in split_multi(str(value or ""), seps=(";", ",")):
        raw = part.split(":", 1)[1] if ":" in part else part
        k = "".join(ch for ch in raw.upper() if ch.isalnum())
        if len(k) >= 5:
            keys.add(k)
    return keys


# ---------------------------------------------------------------------- #
_index: Optional[ScreeningIndex] = None
_index_source: Optional[int] = None
_lock = threading.Lock()


def get_index() -> ScreeningIndex:
    """Return the index for the currently loaded list, rebuilding when the list changes."""
    global _index, _index_source
    df = SanctionsLoader.load()
    if _index is not None and _index_source == id(df):
        return _index
    with _lock:
        if _index is not None and _index_source == id(df):
            return _index
        version = SanctionsLoader.current_version()
        _index = ScreeningIndex(df, version)
        _index_source = id(df)
        return _index


def reset_index() -> None:
    global _index, _index_source
    _index, _index_source = None, None
