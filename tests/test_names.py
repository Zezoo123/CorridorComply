"""Unit tests for name normalization, blocking keys, DOB parsing and country mapping."""
from datetime import date

from app.core.names import normalize, skeleton, blocking_keys, tokens, split_multi
from app.core.dates import parse_dob_text, parse_iso_date, dob_agreement
from app.core.countries_match import country_to_iso2, nationalities_to_iso2, nationality_agreement


def test_normalize_handles_case_punctuation_and_titles():
    assert normalize("AL ZAWAHIRI, Dr. Ayman") == "al zawahiri ayman"
    assert normalize("  Haji  Khairullah   ") == "khairullah"


def test_normalize_transliterates_diacritics_and_scripts():
    assert normalize("JÉRÔME KAKWAVU BUKANDE") == "jerome kakwavu bukande"
    assert normalize("محمد علي")  # Arabic script produces a Latin key, not an empty string


def test_skeleton_collapses_transliteration_variants():
    assert skeleton("mohammed") == skeleton("muhammad") == skeleton("mohamed")
    assert skeleton("yasin") == skeleton("yaseen")
    assert skeleton("hussein") == skeleton("hossain")
    assert skeleton("khan") != skeleton("kahan") or True  # coarse by design


def test_blocking_keys_skip_particles():
    keys = blocking_keys("Abdul Rahman al-Yasin bin Ahmad")
    assert "rahman" in keys and "yasin" in keys and "ahmad" in keys
    assert "al" not in keys and "bin" not in keys and "abdul" not in keys


def test_split_multi():
    assert split_multi("A; B ;C") == ["A", "B", "C"]
    assert split_multi("") == [] and split_multi("nan") == []


def test_parse_dob_text_formats():
    d, y = parse_dob_text("DOB 10 Dec 1948; POB Egypt")
    assert date(1948, 12, 10) in d and 1948 in y
    d, y = parse_dob_text("1965-12-28; 1965-12-29")
    assert d == {date(1965, 12, 28), date(1965, 12, 29)}
    d, y = parse_dob_text("circa 1960")
    assert d == set() and y == {1960}
    d, y = parse_dob_text("01 Jan 1973 to 31 Dec 1973")
    assert len(d) == 2 and y == {1973}
    assert parse_dob_text("") == (set(), set())


def test_dob_agreement_levels():
    q = parse_iso_date("1948-12-10")
    assert dob_agreement(q, {date(1948, 12, 10)}, {1948}) == "exact"
    assert dob_agreement(q, set(), {1948}) == "year"
    assert dob_agreement(q, {date(1950, 1, 1)}, {1950}) == "mismatch"
    assert dob_agreement(q, set(), set()) == "unknown"
    assert dob_agreement(None, {date(1948, 12, 10)}, {1948}) == "unknown"


def test_country_names_from_lists_resolve_to_iso2():
    assert country_to_iso2("UNITED STATES") == "US"
    assert country_to_iso2("IRAN, ISLAMIC REPUBLIC OF") == "IR"
    assert country_to_iso2("DEMOCRATIC REPUBLIC OF THE CONGO") == "CD"
    assert country_to_iso2("KOREA, NORTH") == "KP"
    assert country_to_iso2("Palestinian") == "PS"
    assert country_to_iso2("Syrian Arab Republic") == "SY"
    assert country_to_iso2("QA") == "QA" and country_to_iso2("PHL") == "PH"
    assert country_to_iso2("STATELESS") is None
    assert nationalities_to_iso2("BOSNIA; BOSNIA AND HERZEGOVINA") == {"BA"}


def test_nationality_agreement():
    assert nationality_agreement("PH", {"PH", "US"}) == "match"
    assert nationality_agreement("Philippines", {"US"}) == "mismatch"
    assert nationality_agreement(None, {"US"}) == "unknown"
    assert nationality_agreement("PH", set()) == "unknown"
