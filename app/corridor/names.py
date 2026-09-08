"""
Population-aware name handling for screening.

Generic screeners treat every name the same. On these corridors that is the
main source of both false positives and false negatives:

- Filipino names carry the mother's maiden name as a middle name and often a
  compound surname with a particle ("dela Cruz", "de los Santos"). Lists may
  hold the person without the middle name, so screening only the full string
  can miss them.
- South Asian customers may have a single name, a patronymic joined with
  "s/o", "bin", "ibn", or a name that differs between passport and QID in
  transliteration. A single name matches thousands of list entries, so it
  must be screened with a date of birth to mean anything.
- Arabic names carry particles (al, bin, abu, abd) and transliteration
  variants that the core matcher already groups.

expand_variants() returns the strings to screen; the caller screens each and
keeps the best match. flags() tells the engine what to require.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from ..core.names import normalize

FILIPINO_PARTICLES = {"de", "dela", "del", "delos", "delas", "de la", "de los", "de las", "san", "santa", "sto", "sta"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "junior", "senior"}
PATRONYMIC_JOINERS = {"s/o", "d/o", "w/o", "son of", "daughter of", "wife of", "bin", "binti", "binte", "ibn", "bint", "ould", "velayudhan"}


@dataclass
class NameAnalysis:
    population: str
    original: str
    variants: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)      # single_name, patronymic, compound_surname, suffix
    tokens: List[str] = field(default_factory=list)

    def to_dict(self):
        return {"population": self.population, "variants": self.variants, "flags": self.flags}


def population_for(nationality: Optional[str]) -> str:
    n = (nationality or "").upper()
    if n in {"PH"}:
        return "filipino"
    if n in {"PK", "IN", "BD", "NP", "LK", "AF"}:
        return "south_asian"
    if n in {"QA", "SA", "AE", "KW", "BH", "OM", "EG", "SD", "SY", "JO", "LB", "IQ", "YE", "PS", "MA", "DZ", "TN", "LY", "SO"}:
        return "arabic"
    return "generic"


def _clean_tokens(name: str) -> List[str]:
    text = normalize(name)
    return [t for t in text.split() if t]


def _strip_suffix(tokens: List[str]) -> tuple[List[str], bool]:
    if tokens and tokens[-1] in SUFFIXES:
        return tokens[:-1], True
    return tokens, False


def analyze(name: str, nationality: Optional[str] = None) -> NameAnalysis:
    pop = population_for(nationality)
    a = NameAnalysis(population=pop, original=name)
    tokens = _clean_tokens(name)
    tokens, had_suffix = _strip_suffix(tokens)
    if had_suffix:
        a.flags.append("suffix")
    a.tokens = tokens
    full = " ".join(tokens)
    variants = [full] if full else []

    raw_lower = " " + (name or "").lower() + " "
    if any(f" {j} " in raw_lower for j in PATRONYMIC_JOINERS):
        a.flags.append("patronymic")
        # Screen the part before the joiner on its own too (the person's own name)
        m = re.split(r"\b(?:s/o|d/o|w/o|son of|daughter of|wife of|bin|binti|binte|ibn|bint)\b", (name or "").lower(), maxsplit=1)
        own = _clean_tokens(m[0]) if m else []
        if own and " ".join(own) != full:
            variants.append(" ".join(own))

    if len(tokens) == 1:
        a.flags.append("single_name")

    if pop == "filipino" and len(tokens) >= 3:
        # given names + middle (mother's maiden) + surname; try without the middle name
        # and handle compound surname particles ("dela cruz" -> keep together).
        sur_start = len(tokens) - 1
        while sur_start - 1 >= 1 and tokens[sur_start - 1] in FILIPINO_PARTICLES:
            sur_start -= 1
        if sur_start < len(tokens) - 1:
            a.flags.append("compound_surname")
        surname = tokens[sur_start:]
        given = tokens[:sur_start]
        if len(given) >= 2:
            without_middle = " ".join(given[:-1] + surname)
            if without_middle != full:
                variants.append(without_middle)
            first_and_surname = " ".join([given[0]] + surname)
            if first_and_surname not in variants:
                variants.append(first_and_surname)

    if pop == "south_asian" and len(tokens) >= 3 and "patronymic" not in a.flags:
        # Many South Asian names are written first + father's name + family name;
        # lists often hold first + family. Try dropping the middle token.
        variants.append(" ".join([tokens[0], tokens[-1]]))

    # Dedupe, keep order
    seen = set()
    a.variants = [v for v in variants if v and not (v in seen or seen.add(v))]
    return a
