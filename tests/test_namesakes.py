"""Common-name customers must not become high-risk hits through shortened name variants."""
from app.core.names import normalize
from app.services.aml_service import AMLService
from tests.conftest import add_list_entry


def test_honorific_that_is_also_a_name_is_kept():
    assert normalize("Ahmed Mahmoud El Sayed") == "ahmed mahmoud el sayed"
    assert normalize("Sayed Ahmed") == "sayed ahmed"
    assert normalize("Sayyid Ali Khamenei") == "ali khamenei"
    assert normalize("Dr Hafiz Saeed") == "hafiz saeed"
    assert normalize("Mr Jonathan Whitfield") == "jonathan whitfield"


def test_shortened_variant_hit_is_dropped_when_dob_and_nationality_contradict(sanctions_data_dir):
    add_list_entry(sanctions_data_dir, name="NAIB IMAM", aliases="KHAN MUHAMMAD; KHAN MOHAMMAD",
                   dob="1960-01-01", nationality="AFGHANISTAN", dataid="801")
    r = AMLService.screen_sync("Muhammad Imran Khan", dob="1990-05-03", nationality="PK")
    assert r["sanctions_match"] is False, [m["sanctioned_name"] for m in r["matches"]]
    # An entry with no date of birth and no nationality cannot be excluded on data: shown, but low.
    add_list_entry(sanctions_data_dir, name="KHAN MUHAMMAD", dataid="802")
    r = AMLService.screen_sync("Muhammad Imran Khan", dob="1990-05-03", nationality="PK")
    assert r["sanctions_match"] is True and len(r["matches"]) == 1
    m = r["matches"][0]
    assert m["sanctioned_name"] == "KHAN MUHAMMAD"
    assert m["screened_as"] == "muhammad khan" and m["variant_similarity"] == 100
    assert m["similarity"] < 85 and m["confidence"] == "low"
    assert r["risk_level"].value == "low"
    # A shortened form that is itself only a fuzzy match, with nothing to corroborate it, is noise.
    add_list_entry(sanctions_data_dir, name="MUHAMMAD KANJO", dataid="803")   # replaces the 802 file
    r = AMLService.screen_sync("Muhammad Imran Khan", dob="1990-05-03", nationality="PK")
    assert r["sanctions_match"] is False, [m["sanctioned_name"] for m in r["matches"]]


def test_shortened_variant_hit_stays_when_corroborated(sanctions_data_dir):
    # MARIA SANTOS, PH, 1985-02-14 is in the sample list; the Filipino middle name is dropped.
    r = AMLService.screen_sync("Maria Clara Santos", dob="1985-02-14", nationality="PH")
    assert r["sanctions_match"] is True and r["matches"][0]["sanctioned_name"] == "MARIA SANTOS"
    assert r["matches"][0]["screened_as"] == "maria santos"
    r = AMLService.screen_sync("Maria Clara Santos", nationality="PH")                     # no DOB given, exact short form
    assert r["sanctions_match"] is True
    r = AMLService.screen_sync("Maria Clara Santos", dob="1991-06-12", nationality="PH")   # full dates differ: a namesake
    assert r["sanctions_match"] is False
    r = AMLService.screen_sync("Maria Clara Santos", nationality="BR")                     # nationality differs
    assert r["sanctions_match"] is False


def test_full_name_match_with_wrong_dob_is_demoted_not_hidden(sanctions_data_dir):
    r = AMLService.screen_sync("Mohammad Reza Naqdi", dob="1990-01-01", nationality="PK")
    assert r["sanctions_match"] is True
    assert r["risk_level"].value == "medium"
    assert any("differs" in d for d in r["details"])


def test_name_match_with_wrong_dob_is_low_unless_near_exact(sanctions_data_dir):
    # 100 on the name, DOB differs: medium at most (a data error on either side is possible)
    r = AMLService.screen_sync("Mohammad Reza Naqdi", dob="1990-01-01", nationality="IR")
    assert r["risk_level"].value == "medium" and r["risk_score"] <= 69
    # a fuzzy name match (below 95) with a differing DOB is a namesake: low
    add_list_entry(sanctions_data_dir, name="MOHAMMAD ALI JAFARI", dob="1950-05-05", nationality="IRAN", dataid="810")
    r = AMLService.screen_sync("Mohammad Arif Ali", dob="1987-03-20", nationality="IR")
    assert r["sanctions_match"] is True
    assert r["risk_level"].value == "low", (r["risk_score"], [m["sanctioned_name"] for m in r["matches"]])
    assert any("Capped" in d for d in r["details"])


def test_partial_name_match_needs_the_date_of_birth(sanctions_data_dir):
    add_list_entry(sanctions_data_dir, name="MOHAMMED YAHYA MUJAHID", dob="1970-06-01", nationality="PAKISTAN", dataid="820")
    # fewer tokens than the list holds, DOB agrees: found, as a partial match, never high on the name alone
    r = AMLService.screen_sync("Mohammed Mujahid", dob="1970-06-01", nationality="PK")
    assert r["sanctions_match"] is True
    m = r["matches"][0]
    assert m["sanctioned_name"] == "MOHAMMED YAHYA MUJAHID" and m["match_type"] == "partial"
    assert m["similarity"] <= 94 and m["dob_agreement"] == "exact"
    assert any("part of a listed name" in d for d in r["details"])
    # same tokens, year agrees only: still found, but never high
    r = AMLService.screen_sync("Mujahid Mohammed", dob="1970-01-01", nationality="PK")
    assert r["sanctions_match"] is True and r["risk_level"].value == "medium"
    # tokens collected across different aliases of one entry do not make a partial match
    add_list_entry(sanctions_data_dir, name="ONE-P", aliases="Mohammed; Iqbal; Khan", dob="1970-06-01", dataid="821")
    assert AMLService.screen_sync("Mohammed Iqbal Khan", dob="1970-06-01", nationality="PK")["sanctions_match"] is False
    # no DOB, or a differing DOB: a subset of common tokens is not evidence
    assert AMLService.screen_sync("Mohammed Mujahid", nationality="PK")["sanctions_match"] is False
    assert AMLService.screen_sync("Mohammed Mujahid", dob="1991-03-03", nationality="PK")["sanctions_match"] is False
    # a single token is never enough
    assert AMLService.screen_sync("Mujahid", dob="1970-06-01", nationality="PK")["sanctions_match"] is False
