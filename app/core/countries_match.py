"""
Map the free-text country names used by sanctions lists to ISO alpha-2 codes.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional, Set

from rapidfuzz import fuzz, process

from ..data.countries import COUNTRIES, get_country_info
from .names import normalize, split_multi

# Names that appear on the lists and are not the ISO short name.
_SYNONYMS = {
    "united states": "US", "usa": "US", "u s a": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "england": "GB",
    "russia": "RU", "russian federation": "RU", "ussr": "RU", "soviet union": "RU",
    "iran": "IR", "syria": "SY", "north korea": "KP", "dprk": "KP", "korea north": "KP",
    "korea democratic peoples republic of": "KP", "south korea": "KR", "korea south": "KR",
    "korea republic of": "KR", "venezuela": "VE", "bolivia": "BO", "tanzania": "TZ",
    "united republic of tanzania": "TZ", "laos": "LA", "vietnam": "VN", "viet nam": "VN",
    "moldova": "MD", "macedonia": "MK", "north macedonia": "MK", "czech republic": "CZ",
    "czechia": "CZ", "turkey": "TR", "turkiye": "TR", "palestine": "PS", "palestinian": "PS",
    "gaza": "PS", "west bank": "PS", "democratic republic of the congo": "CD", "drc": "CD",
    "congo democratic republic": "CD", "congo democratic republic of the": "CD",
    "republic of the congo": "CG", "congo": "CG", "ivory coast": "CI", "cote divoire": "CI",
    "burma": "MM", "myanmar": "MM", "libya": "LY", "libyan arab jamahiriya": "LY",
    "bosnia": "BA", "bosnia and herzegovina": "BA", "brunei": "BN", "cape verde": "CV",
    "swaziland": "SZ", "eswatini": "SZ", "micronesia": "FM", "kosovo": "XK",
    "uae": "AE", "united arab emirates": "AE", "ksa": "SA", "saudi arabia": "SA",
    "hong kong": "HK", "macau": "MO", "macao": "MO", "taiwan": "TW", "china": "CN",
    "peoples republic of china": "CN", "prc": "CN", "vatican": "VA", "holy see": "VA",
    "east timor": "TL", "timor leste": "TL", "the gambia": "GM", "gambia": "GM",
    "the bahamas": "BS", "bahamas": "BS", "netherlands": "NL", "holland": "NL",
    "philippines": "PH", "the philippines": "PH", "pakistan": "PK", "bangladesh": "BD",
    "india": "IN", "qatar": "QA", "egypt": "EG", "stateless": "",
}

_CHOICES = {normalize(info["name"]): code for code, info in COUNTRIES.items()}
_CHOICES.update({k: v for k, v in _SYNONYMS.items() if v})


@lru_cache(maxsize=4096)
def country_to_iso2(value: str) -> Optional[str]:
    """Resolve an ISO code or a country name (any casing, list-style) to alpha-2."""
    if not value:
        return None
    raw = str(value).strip()
    info = get_country_info(raw)
    if info and len(raw) in (2, 3):
        return info["alpha2"]
    key = normalize(raw)
    if not key:
        return None
    if key in _SYNONYMS:
        return _SYNONYMS[key] or None
    if key in _CHOICES:
        return _CHOICES[key]
    match = process.extractOne(key, list(_CHOICES.keys()), scorer=fuzz.token_set_ratio, score_cutoff=90)
    if match:
        return _CHOICES[match[0]]
    return None


def nationalities_to_iso2(field: str) -> Set[str]:
    """A list entry's multi-valued nationalities field as a set of alpha-2 codes."""
    codes: Set[str] = set()
    for part in split_multi(field):
        code = country_to_iso2(part)
        if code:
            codes.add(code)
    return codes


def nationality_agreement(query: Optional[str], entry_codes: Set[str]) -> str:
    if not query:
        return "unknown"
    code = country_to_iso2(query)
    if not code or not entry_codes:
        return "unknown"
    return "match" if code in entry_codes else "mismatch"
