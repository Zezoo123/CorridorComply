"""Corridor engine: identifiers, names, rules, decision endpoint."""
import json

import pytest

from app.corridor import engine as corridor_engine
from app.corridor.identifiers import check_id, verhoeff_generate
from app.corridor.names import analyze
from app.corridor.schema import Ruleset

RULES_DIR = "tests/data/corridor_rules"


@pytest.fixture
def test_rules(monkeypatch):
    monkeypatch.setenv("CORRIDOR_RULES_DIR", RULES_DIR)
    corridor_engine.reset_registry()
    yield corridor_engine.registry()
    corridor_engine.reset_registry()


# ------------------------------------------------------------ identifiers
def test_qatar_id_encodes_birth_year_and_nationality():
    c = check_id("qatar_id", "28560812345")
    assert c.valid and c.facts == {"birth_year": 1985, "nationality": "PH"}
    c = check_id("qatar_id", "30158612345")
    assert c.valid and c.facts["birth_year"] == 2001 and c.facts["nationality"] == "PK"
    assert not check_id("qatar_id", "1234567890").valid
    assert not check_id("qatar_id", "48560812345").valid


def test_pakistan_cnic():
    c = check_id("pk_cnic", "42101-1234567-1")
    assert c.valid and c.facts["sex"] == "male" and c.normalized == "42101-1234567-1"
    assert check_id("pk_cnic", "4210112345672").facts["sex"] == "female"
    assert not check_id("pk_cnic", "9210112345672").valid
    assert not check_id("pk_cnic", "42101-123456-1").valid


def test_aadhaar_verhoeff():
    # 9999 4105 7058 is the sample number in UIDAI documentation
    assert check_id("in_aadhaar", "9999 4105 7058").valid
    assert not check_id("in_aadhaar", "999941057050").valid
    assert not check_id("in_aadhaar", "199941057058").valid
    base = "23456789012"
    assert check_id("in_aadhaar", base + verhoeff_generate(base)).valid


def test_bangladesh_nid_and_philsys_and_passports():
    assert check_id("bd_nid", "1234567890").valid
    assert check_id("bd_nid", "19901234567890123").facts["birth_year"] == 1990
    assert not check_id("bd_nid", "123456789").valid
    assert check_id("ph_philsys", "1234-5678-9012-3456").normalized == "1234-5678-9012-3456"
    assert check_id("passport", "P1234567A", "PH").valid
    assert not check_id("passport", "12345", "PH").valid
    assert check_id("passport", "AB1234567", "PK").valid
    unknown = check_id("passport", "X123456", "ZZ")
    assert unknown.valid and unknown.facts["format_known"] is False
    assert check_id("ph_umid", "anything").valid  # no validator: not checked, not failed


# ------------------------------------------------------------------ names
def test_filipino_name_variants_drop_middle_name_and_keep_compound_surname():
    a = analyze("Maria Clara Santos dela Cruz", "PH")
    assert a.population == "filipino"
    assert "compound_surname" in a.flags
    assert a.variants == ["maria clara santos dela cruz", "maria clara dela cruz", "maria dela cruz"]


def test_south_asian_patronymic_and_single_name():
    a = analyze("Muhammad Imran s/o Abdul Rasheed", "PK")
    assert "patronymic" in a.flags and "muhammad imran" in a.variants
    b = analyze("Ramesh", "IN")
    assert b.flags == ["single_name"] and b.variants == ["ramesh"]
    c = analyze("Rahul Kumar Sharma", "IN")
    assert "rahul sharma" in c.variants


def test_suffix_is_stripped():
    a = analyze("Jose Reyes Jr.", "PH")
    assert "suffix" in a.flags and a.variants[0] == "jose reyes"


def test_screening_uses_variants_to_catch_a_listed_person(sanctions_data_dir):
    from app.services.aml_service import AMLService
    r = AMLService.screen_sync("Maria Clara Santos", nationality="PH", dob="1985-02-14")
    assert r["sanctions_match"] is True
    assert r["matches"][0]["sanctioned_name"] == "MARIA SANTOS"
    assert "maria santos" in r["screened_variants"]
    r2 = AMLService.screen_sync("Maria Clara Santos", nationality="PH", use_variants=False)
    assert r2["sanctions_match"] is False


# ----------------------------------------------------------------- schema
def test_ruleset_rejects_unknown_field_and_bad_id():
    base = json.load(open(f"{RULES_DIR}/xx_yy_rules.json"))
    bad = dict(base); bad["rules"] = [dict(base["rules"][0])]
    bad["rules"][0] = {**bad["rules"][0], "when": {"all": [{"field": "customer.shoe_size", "op": "eq", "value": 1}]}}
    with pytest.raises(Exception) as e:
        Ruleset.model_validate(bad)
    assert "unknown field" in str(e.value)
    bad2 = dict(base); bad2["id"] = "QA-PH"
    with pytest.raises(Exception):
        Ruleset.model_validate(bad2)
    bad3 = dict(base); bad3["status"] = "approved"
    with pytest.raises(Exception) as e3:
        Ruleset.model_validate(bad3)
    assert "reviewed_by" in str(e3.value)


def test_shipped_qa_ph_ruleset_is_valid_and_draft():
    corridor_engine.reset_registry()
    reg = corridor_engine.registry()
    rs = reg.get("QA-PH")
    assert rs.status == "draft" and rs.reviewed_by is None
    assert rs.sending.country == "QA" and rs.receiving.country == "PH"
    assert any(r.id == "sanctions-true-match" for r in rs.rules)
    assert reg.errors == {}
    corridor_engine.reset_registry()


# ----------------------------------------------------------------- engine
def _screen(match=True, confidence="high", dob="exact"):
    if not match:
        return {"sanctions_match": False, "risk_score": 0, "matches": []}
    return {"sanctions_match": True, "risk_score": 80,
            "matches": [{"confidence": confidence, "similarity": 100, "dob_agreement": dob, "country_match": True,
                         "match_type": "name", "source": "UN"}]}


def test_engine_outcome_is_most_severe_and_reasons_are_all(test_rules):
    rs = test_rules.get("XX-YY")
    d = corridor_engine.decide(rs, {"full_name": "A B", "dob": "1990-01-01"}, _screen())
    assert d["outcome"] == "reject"
    assert [r["rule"] for r in d["reasons"]] == ["true-match", "any-hit"]
    assert d["risk_score"] == 100 and d["actions"] == ["freeze_and_report"]

    d = corridor_engine.decide(rs, {"full_name": "A B", "dob": "1990-01-01"}, _screen(dob="mismatch"))
    assert d["outcome"] == "review" and [r["rule"] for r in d["reasons"]] == ["any-hit"]

    d = corridor_engine.decide(rs, {"full_name": "A B", "dob": "1990-01-01"}, _screen(match=False))
    assert d["outcome"] == "approve" and d["reasons"] == [] and d["risk_score"] == 0


def test_engine_missing_fields_and_transfer_threshold(test_rules):
    rs = test_rules.get("XX-YY")
    d = corridor_engine.decide(rs, {"full_name": "A B"}, _screen(match=False))
    assert d["outcome"] == "review" and d["facts"]["customer.missing_fields"] == ["dob"]
    d = corridor_engine.decide(rs, {"full_name": "A B", "dob": "1990-01-01"}, _screen(match=False), transfer={"amount": 60000})
    assert [r["rule"] for r in d["reasons"]] == ["big-transfer"]


def test_changing_a_threshold_in_the_file_changes_the_decision(tmp_path, monkeypatch):
    """Rules are data: no code change needed to move a threshold."""
    src = json.load(open(f"{RULES_DIR}/xx_yy_rules.json"))
    for amount, expected in ((50000, "review"), (70000, "approve")):
        rules = json.loads(json.dumps(src))
        rules["rules"][3]["when"]["all"][0]["value"] = amount
        d = tmp_path / f"r{amount}"; d.mkdir()
        (d / "xx_yy_rules.json").write_text(json.dumps(rules))
        monkeypatch.setenv("CORRIDOR_RULES_DIR", str(d))
        corridor_engine.reset_registry()
        rs = corridor_engine.registry().get("XX-YY")
        out = corridor_engine.decide(rs, {"full_name": "A B", "dob": "1990-01-01"}, _screen(match=False), transfer={"amount": 60000})
        assert out["outcome"] == expected
    corridor_engine.reset_registry()


def test_invalid_ruleset_file_is_reported_not_loaded(tmp_path, monkeypatch):
    (tmp_path / "bad_rules.json").write_text('{"id": "AA-BB"}')
    monkeypatch.setenv("CORRIDOR_RULES_DIR", str(tmp_path))
    corridor_engine.reset_registry()
    reg = corridor_engine.registry()
    assert reg.list() == [] and "bad_rules.json" in reg.errors
    corridor_engine.reset_registry()


# -------------------------------------------------------------------- API
def test_decision_endpoint_end_to_end(client):
    corridor_engine.reset_registry()  # use the shipped QA-PH ruleset
    payload = {
        "corridor": "QA-PH",
        "customer": {"full_name": "Abdul Rahman Yasin", "dob": "1960-04-10", "nationality": "IQ",
                     "document_type": "qatar_id", "document_number": "26036812345", "document_expiry": "2028-01-01",
                     "mobile": "+974", "address_qatar": "Doha", "purpose": "family support", "reference": "CUST-9"},
        "beneficiary": {"full_name": "Maria Reyes", "country": "PH", "relationship": "spouse", "payout_channel": "cash",
                        "id_type": "ph_philsys", "id_number": "1234-5678-9012-3456"},
        "kyc": {"document_verified": True, "face_match": True, "document_expired": False},
        "transfer": {"amount": 2000, "currency": "QAR"},
    }
    r = client.post("/api/v1/decision", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "reject"
    rules = [x["rule"] for x in body["reasons"]]
    assert "sanctions-true-match" in rules
    assert "freeze_and_report" in body["actions"]
    assert body["ruleset_status"] == "draft"
    assert body["id_check"]["facts"] == {"birth_year": 1960, "nationality": "IQ"}
    assert body["beneficiary_id_check"]["valid"] is True
    assert body["list_version"] and body["screening_id"] and body["decision_id"]

    # stored, listable, and the customer is on file for monitoring
    d = client.get(f"/api/v1/decisions/{body['decision_id']}").json()
    assert d["outcome"] == "reject" and d["customer"]["full_name"] == "Abdul Rahman Yasin"
    assert client.get("/api/v1/decisions?outcome=reject").json()["count"] == 1
    assert any(c["reference"] == "CUST-9" for c in client.get("/api/v1/customers").json()["customers"])


def test_decision_clean_customer_with_qid_mismatch(client):
    corridor_engine.reset_registry()
    payload = {"corridor": "QA-PH",
               "customer": {"full_name": "Jonathan Whitfield", "dob": "1979-02-03", "nationality": "GB",
                            "document_type": "qatar_id", "document_number": "28560812345",  # encodes 1985 / PH
                            "document_expiry": "2028-01-01", "mobile": "x", "address_qatar": "x", "purpose": "x"}}
    body = client.post("/api/v1/decision", json=payload).json()
    assert body["outcome"] == "review"
    rules = {x["rule"] for x in body["reasons"]}
    assert rules == {"qid-birth-year-mismatch", "qid-nationality-mismatch"}
    assert body["screening"]["sanctions_match"] is False


def test_decision_approve_when_everything_is_clean(client):
    corridor_engine.reset_registry()
    payload = {"corridor": "QA-PH",
               "customer": {"full_name": "Jonathan Whitfield", "dob": "1979-02-03", "nationality": "GB",
                            "document_type": "passport", "document_number": "123456789", "document_expiry": "2030-01-01",
                            "mobile": "x", "address_qatar": "x", "purpose": "x"}}
    body = client.post("/api/v1/decision", json=payload).json()
    assert body["outcome"] == "approve" and body["reasons"] == [] and body["risk_score"] == 0


def test_corridors_listing_and_unknown_corridor(client):
    corridor_engine.reset_registry()
    listing = client.get("/api/v1/corridors").json()
    assert any(c["id"] == "QA-PH" and c["status"] == "draft" for c in listing["corridors"])
    assert client.get("/api/v1/corridors/QA-PH").json()["sending"]["country"] == "QA"
    assert client.get("/api/v1/corridors/ZZ-ZZ").status_code == 404
    assert "screening.best_confidence" in client.get("/api/v1/corridors/fields").json()["fields"]
    r = client.post("/api/v1/decision", json={"corridor": "ZZ-ZZ", "customer": {"full_name": "A B"}})
    assert r.status_code == 404
