"""
Identity-number validators for the corridors CorridorComply serves.

Each validator returns an IdCheck. "valid" means the number is well-formed per
the published format; it never means the document is genuine. Where a format
encodes facts (Qatar ID encodes birth year and nationality, Pakistani CNIC
encodes sex, Aadhaar carries a Verhoeff check digit) the validator extracts
them so the corridor engine can cross-check against what the customer stated.

Formats are from public specifications; treat them as version-zero and keep
the sources list in docs/corridor_rules.md current.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..data.countries import COUNTRIES


@dataclass
class IdCheck:
    id_type: str
    valid: bool
    normalized: str = ""
    reasons: List[str] = field(default_factory=list)
    facts: Dict[str, object] = field(default_factory=dict)   # e.g. birth_year, nationality, sex

    def to_dict(self) -> Dict[str, object]:
        return {"id_type": self.id_type, "valid": self.valid, "normalized": self.normalized,
                "reasons": self.reasons, "facts": self.facts}


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


# ISO 3166-1 numeric codes for the nationalities that matter on these corridors.
# (The countries table carries alpha codes only; numeric is needed for the QID.)
ISO_NUMERIC = {
    "004": "AF", "050": "BD", "064": "BT", "356": "IN", "364": "IR", "368": "IQ", "400": "JO", "414": "KW",
    "422": "LB", "144": "LK", "458": "MY", "462": "MV", "524": "NP", "512": "OM", "586": "PK", "608": "PH",
    "634": "QA", "682": "SA", "706": "SO", "729": "SD", "760": "SY", "784": "AE", "818": "EG", "887": "YE",
    "404": "KE", "800": "UG", "834": "TZ", "231": "ET", "232": "ER", "566": "NG", "288": "GH", "120": "CM",
    "360": "ID", "764": "TH", "704": "VN", "116": "KH", "104": "MM", "156": "CN", "826": "GB", "840": "US",
    "124": "CA", "036": "AU", "276": "DE", "250": "FR", "380": "IT", "724": "ES", "792": "TR", "788": "TN",
    "012": "DZ", "504": "MA", "434": "LY", "048": "BH", "275": "PS", "398": "KZ", "860": "UZ", "643": "RU",
    "804": "UA", "608 ": "PH",
}


# ---------------------------------------------------------------- Qatar ID
def qatar_id(value: str) -> IdCheck:
    """Qatar ID (QID): 11 digits. Digit 1 is the birth century (2 = 19xx, 3 = 20xx),
    digits 2-3 the birth year, digits 4-6 the ISO numeric code of the holder's
    nationality, digits 7-11 a serial. Facts extracted: birth_year, nationality."""
    d = _digits(value)
    c = IdCheck("qatar_id", False, d)
    if len(d) != 11:
        c.reasons.append(f"expected 11 digits, got {len(d)}")
        return c
    if d[0] not in "23":
        c.reasons.append("first digit must be 2 (born 19xx) or 3 (born 20xx)")
        return c
    century = 1900 if d[0] == "2" else 2000
    c.facts["birth_year"] = century + int(d[1:3])
    nat = ISO_NUMERIC.get(d[3:6])
    if nat:
        c.facts["nationality"] = nat
    else:
        c.facts["nationality_code"] = d[3:6]
        c.reasons.append(f"nationality code {d[3:6]} not in the corridor table (format still valid)")
    c.valid = True
    return c


# ------------------------------------------------------------ Pakistan CNIC
def pakistan_cnic(value: str) -> IdCheck:
    """CNIC: 13 digits, written 12345-1234567-1. Digit 1 is the province/region
    of registration (1-7); the last digit is odd for male, even for female."""
    d = _digits(value)
    c = IdCheck("pk_cnic", False, d)
    if len(d) != 13:
        c.reasons.append(f"expected 13 digits, got {len(d)}")
        return c
    if d[0] not in "1234567":
        c.reasons.append("first digit is not a valid registration region")
        return c
    c.facts["sex"] = "male" if int(d[-1]) % 2 == 1 else "female"
    c.facts["region_code"] = d[0]
    c.normalized = f"{d[:5]}-{d[5:12]}-{d[12]}"
    c.valid = True
    return c


# ----------------------------------------------------------- India Aadhaar
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_checksum_ok(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_generate(number_without_check: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(number_without_check)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(ch)]]
    return str(_VERHOEFF_INV[c])


def india_aadhaar(value: str) -> IdCheck:
    """Aadhaar: 12 digits, first digit 2-9, last digit a Verhoeff check digit.
    Note: Indian law restricts collecting Aadhaar; prefer the last-4 masked form
    or another ID in a remittance flow. Validator provided for completeness."""
    d = _digits(value)
    c = IdCheck("in_aadhaar", False, d)
    if len(d) != 12:
        c.reasons.append(f"expected 12 digits, got {len(d)}")
        return c
    if d[0] in "01":
        c.reasons.append("first digit must be 2-9")
        return c
    if not verhoeff_checksum_ok(d):
        c.reasons.append("Verhoeff check digit does not match")
        return c
    c.normalized = f"{d[:4]} {d[4:8]} {d[8:]}"
    c.valid = True
    return c


# ---------------------------------------------------------- Bangladesh NID
def bangladesh_nid(value: str) -> IdCheck:
    """NID: 10 digits (smart card), 13 digits (older) or 17 digits (13-digit
    number prefixed with the 4-digit birth year). Facts: birth_year for 17-digit."""
    d = _digits(value)
    c = IdCheck("bd_nid", False, d)
    if len(d) not in (10, 13, 17):
        c.reasons.append(f"expected 10, 13 or 17 digits, got {len(d)}")
        return c
    if len(d) == 17:
        year = int(d[:4])
        if not 1900 <= year <= 2100:
            c.reasons.append("17-digit NID must start with the birth year")
            return c
        c.facts["birth_year"] = year
    c.valid = True
    return c


# ---------------------------------------------------------- Philippines
def philsys_pcn(value: str) -> IdCheck:
    """PhilSys Card Number: 16 digits printed as 1234-5678-9012-3456. No public
    check digit; format only."""
    d = _digits(value)
    c = IdCheck("ph_philsys", False, d)
    if len(d) != 16:
        c.reasons.append(f"expected 16 digits, got {len(d)}")
        return c
    c.normalized = "-".join(d[i:i + 4] for i in range(0, 16, 4))
    c.valid = True
    return c


# ---------------------------------------------------------- Passports
_PASSPORT_PATTERNS = {
    "PH": re.compile(r"^[A-Z]{1,2}\d{7}[A-Z]?$"),   # e.g. P1234567A
    "PK": re.compile(r"^[A-Z]{2}\d{7}$"),
    "IN": re.compile(r"^[A-Z]\d{7}$"),
    "BD": re.compile(r"^[A-Z]{1,2}\d{7,8}$"),
    "NP": re.compile(r"^\d{8}$|^[A-Z]{2}\d{7}$"),
    "LK": re.compile(r"^[A-Z]\d{7}$"),
    "QA": re.compile(r"^\d{8,9}$"),
    "EG": re.compile(r"^[A-Z]\d{8}$"),
}


def passport_number(value: str, nationality: Optional[str]) -> IdCheck:
    """Passport number shape by issuing country. Low confidence: formats vary by
    passport generation; failing here is a prompt to look, not a rejection."""
    v = re.sub(r"[\s-]", "", (value or "").upper())
    c = IdCheck("passport", False, v)
    if not v:
        c.reasons.append("empty")
        return c
    nat = (nationality or "").upper()
    pat = _PASSPORT_PATTERNS.get(nat)
    if pat is None:
        c.valid = bool(re.match(r"^[A-Z0-9]{6,12}$", v))
        if not c.valid:
            c.reasons.append("6-12 letters or digits expected")
        c.facts["format_known"] = False
        return c
    c.facts["format_known"] = True
    if pat.match(v):
        c.valid = True
    else:
        c.reasons.append(f"does not match the usual {nat} passport format")
    return c


VALIDATORS: Dict[str, Callable[..., IdCheck]] = {
    "qatar_id": qatar_id,
    "pk_cnic": pakistan_cnic,
    "in_aadhaar": india_aadhaar,
    "bd_nid": bangladesh_nid,
    "ph_philsys": philsys_pcn,
}


def check_id(id_type: str, value: str, nationality: Optional[str] = None) -> IdCheck:
    if id_type == "passport":
        return passport_number(value, nationality)
    fn = VALIDATORS.get(id_type)
    if fn is None:
        return IdCheck(id_type, True, (value or "").strip(), reasons=["no validator for this id type; format not checked"],
                       facts={"format_known": False})
    return fn(value)
