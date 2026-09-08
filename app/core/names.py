"""
Name normalization and blocking keys for sanctions screening.

Everything here is deterministic and dependency-light so the same logic can
run inside the API, the batch screener and the tests.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List, Set

from unidecode import unidecode

# Honorifics and ranks that appear in list names but never in a customer record.
_TITLES = {
    "mr", "mrs", "ms", "dr", "prof", "sir", "hajji", "haji", "hajj", "shaykh", "sheikh",
    "sheik", "mullah", "maulavi", "maulawi", "mawlawi", "colonel", "col", "general", "gen",
    "brigadier", "major", "captain", "capt", "lieutenant", "lt", "engineer", "eng",
    "alhaj", "al-haj", "sayed", "sayyed", "sayyid", "seyyed", "ustad", "ustaz", "hafiz", "qari",
}

# Name particles: kept in the string for scoring, but never used as index keys
# because they occur in tens of thousands of names.
PARTICLES = {
    "al", "el", "ul", "bin", "ibn", "bint", "abu", "abou", "abd", "abdul", "abdel", "abdal",
    "ould", "ben", "de", "da", "del", "della", "di", "du", "la", "le", "van", "von", "der",
    "den", "y", "e", "and", "of", "the", "co", "ltd", "llc", "inc", "sa", "plc", "gmbh",
    "company", "corporation", "corp", "limited", "trading", "group", "holding", "holdings",
}

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")


def normalize(name: str) -> str:
    """Lowercase ASCII, punctuation removed, whitespace collapsed, titles stripped.

    Handles diacritics (JÉRÔME -> jerome), Arabic and Cyrillic script via
    transliteration, and OFAC's "LAST, FIRST" comma convention.
    """
    if not name:
        return ""
    text = unicodedata.normalize("NFKC", str(name))
    text = unidecode(text).lower()
    text = text.replace("'", "").replace("’", "")
    text = _NON_ALNUM.sub(" ", text)
    tokens = [t for t in _SPACES.split(text.strip()) if t and t not in _TITLES]
    return " ".join(tokens)


def tokens(name: str) -> List[str]:
    return [t for t in normalize(name).split(" ") if t]


_DIGRAPHS = (
    ("ph", "f"), ("gh", "g"), ("kh", "k"), ("sh", "s"), ("ch", "s"), ("th", "t"),
    ("dh", "d"), ("zh", "z"), ("ck", "k"), ("q", "k"), ("c", "k"), ("x", "ks"),
    ("w", "v"), ("j", "y"),
)
_VOWELS = re.compile(r"[aeiouy]")
_REPEATS = re.compile(r"(.)\1+")


def skeleton(token: str) -> str:
    """Consonant skeleton used as a blocking key for transliteration variants.

    mohammed / muhammad / mohamed -> "mmd"; yasin / yaseen -> "ysn";
    hussein / hossain / husain -> "hsn". Deliberately coarse: it only decides
    which candidates get scored, not whether they match.
    """
    t = token.lower()
    if not t:
        return ""
    for a, b in _DIGRAPHS:
        t = t.replace(a, b)
    first, rest = t[0], t[1:]
    rest = _VOWELS.sub("", rest)
    rest = rest.replace("h", "")
    t = first + rest
    t = _REPEATS.sub(r"\1", t)
    return t


def blocking_keys(name: str) -> Set[str]:
    """Keys under which a name is indexed: its non-particle tokens and their skeletons."""
    keys: Set[str] = set()
    for tok in tokens(name):
        if tok in PARTICLES or len(tok) < 2:
            continue
        keys.add(tok)
        sk = skeleton(tok)
        if len(sk) >= 2:
            keys.add("~" + sk)
    return keys


def split_multi(value: str, seps: Iterable[str] = (";",)) -> List[str]:
    """Split a multi-valued list field ("A; B; C") into clean parts."""
    if not value or str(value).lower() == "nan":
        return []
    text = str(value)
    for s in seps:
        text = text.replace(s, "\x00")
    return [p.strip() for p in text.split("\x00") if p.strip()]
