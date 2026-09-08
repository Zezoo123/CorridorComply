"""
Date-of-birth parsing for sanctions list entries and screening requests.
"""
from __future__ import annotations

import re
from datetime import date
from typing import List, Optional, Set, Tuple

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY_TEXT = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{4})\b")
_MY_TEXT = re.compile(r"\b([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{4})\b")
_DMY_NUM = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")
_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


def parse_dob_text(text: str) -> Tuple[Set[date], Set[int]]:
    """Extract every full date and every year mentioned in a free-text DOB field.

    Accepts ISO dates, "10 Dec 1948", "Dec 1948", "10/12/1948", "circa 1960",
    "01 Jan 1973 to 31 Dec 1973" and semicolon-separated lists of any of these.
    """
    dates: Set[date] = set()
    years: Set[int] = set()
    if not text:
        return dates, years
    text = str(text)
    for y, m, d in _ISO.findall(text):
        try:
            dates.add(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for d, mon, y in _DMY_TEXT.findall(text):
        m = _MONTHS.get(mon.lower())
        if m:
            try:
                dates.add(date(int(y), m, int(d)))
            except ValueError:
                pass
    for d, m, y in _DMY_NUM.findall(text):
        try:
            dates.add(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for y in _YEAR.findall(text):
        years.add(int(y))
    years.update(d.year for d in dates)
    return dates, years


def parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    m = _ISO.search(str(value))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def dob_agreement(query: Optional[date], dates: Set[date], years: Set[int]) -> str:
    """How a submitted DOB relates to a list entry: exact, year, mismatch or unknown."""
    if query is None or (not dates and not years):
        return "unknown"
    if query in dates:
        return "exact"
    if query.year in years:
        return "year"
    return "mismatch"


def format_dates(dates: Set[date], years: Set[int]) -> List[str]:
    out = sorted(d.isoformat() for d in dates)
    out += sorted(str(y) for y in years if y not in {d.year for d in dates})
    return out
