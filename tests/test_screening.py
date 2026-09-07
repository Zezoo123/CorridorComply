"""Tests for the screening index: aliases, entity types, DOB and nationality agreement."""
from app.services.screening import get_index, ScreeningIndex
from app.services.aml_service import AMLService
from app.services.sanctions_loader import SanctionsLoader


def test_index_is_built_once_per_loaded_list(sanctions_data_dir):
    a = get_index()
    b = get_index()
    assert a is b
    assert a.list_version.startswith("combined_sanctions_")
    SanctionsLoader.clear_cache()
    assert get_index() is not a


def test_alias_is_found(sanctions_data_dir):
    hits = get_index().screen("Mohammad Reza Naghdi")
    assert hits and hits[0].entry.name == "MOHAMMAD REZA NAQDI"
    assert hits[0].match_type == "alias"
    assert hits[0].matched_name == "MOHAMMAD REZA NAGHDI"


def test_transliteration_variant_is_found(sanctions_data_dir):
    hits = get_index().screen("Muhammad Riza Naqdi")
    assert hits and hits[0].entry.name == "MOHAMMAD REZA NAQDI"


def test_word_order_and_particles(sanctions_data_dir):
    hits = get_index().screen("Yasin, Abdul Rahman")
    assert hits and hits[0].entry.name == "ABDUL RAHMAN YASIN"


def test_entity_type_filter(sanctions_data_dir):
    idx = get_index()
    assert idx.screen("Bank Mellat", entity_type="person") == []
    assert idx.screen("Mellat Bank", entity_type="entity")[0].entry.name == "BANK MELLAT"
    assert idx.screen("Grace 1", entity_type="vessel")[0].entry.record_type == "vessel"
    assert idx.screen("Adrian Darya 1", entity_type="any")[0].match_type == "alias"


def test_dob_and_nationality_agreement(sanctions_data_dir):
    idx = get_index()
    exact = idx.screen("Abdul Rahman Yasin", dob="1960-04-10", nationality="IQ")[0]
    assert exact.dob_agreement == "exact" and exact.nationality_agreement == "match"
    year = idx.screen("Abdul Rahman Yasin", dob="1960-01-01", nationality="Iraq")[0]
    assert year.dob_agreement == "year" and year.nationality_agreement == "match"
    wrong = idx.screen("Abdul Rahman Yasin", dob="1975-05-05", nationality="PH")[0]
    assert wrong.dob_agreement == "mismatch" and wrong.nationality_agreement == "mismatch"
    unknown = idx.screen("Abdul Rahman Yasin")[0]
    assert unknown.dob_agreement == "unknown" and unknown.nationality_agreement == "unknown"


def test_clean_name_returns_nothing(sanctions_data_dir):
    assert get_index().screen("Jonathan Whitfield") == []
    assert get_index().screen("") == []


def test_dob_mismatch_lowers_risk_for_namesake(sanctions_data_dir):
    same = AMLService.screen_sync("Maria Santos", dob="1985-02-14", nationality="PH")
    other = AMLService.screen_sync("Maria Santos", dob="1999-09-09", nationality="PH")
    assert same["risk_score"] > other["risk_score"]
    assert same["matches"][0]["dob_match"] is True
    assert other["matches"][0]["dob_match"] is False
    assert same["list_version"] == other["list_version"]


def test_index_builds_from_dataframe_directly(sanctions_data_dir):
    df = SanctionsLoader.load()
    idx = ScreeningIndex(df, "test")
    assert len(idx.entries) == len(df)
    assert all(e.variants for e in idx.entries)
