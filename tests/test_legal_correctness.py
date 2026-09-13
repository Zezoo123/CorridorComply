"""Beneficiary screening, country risk, internal watchlist, OFAC consolidated list."""
import re
from datetime import datetime

from app.corridor import engine as corridor_engine
from app.data.countries import country_risk, risk_lists
from tests.conftest import SAMPLE_COMBINED_CSV


def _customer(**kw):
    base = {"full_name": "Jonathan Whitfield", "dob": "1979-02-03", "place_of_birth": "Leeds", "nationality": "GB",
            "document_type": "passport", "document_number": "123456789", "document_expiry": "2030-01-01", "mobile": "x",
            "address_qatar": "x", "profession": "engineer", "employer_sponsor": "Acme", "purpose": "family support",
            "is_resident": False}
    base.update(kw)
    return base


def _decide(client, customer, beneficiary=None, transfer=None):
    corridor_engine.reset_registry()
    body = {"corridor": "QA-PH", "customer": customer}
    if beneficiary:
        body["beneficiary"] = beneficiary
    if transfer:
        body["transfer"] = transfer
    r = client.post("/api/v1/decision", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------ beneficiary
def test_listed_beneficiary_is_rejected(client):
    ben = {"full_name": "Abdul Rahman Yasin", "country": "IQ", "dob": "1960-04-10", "relationship": "brother", "payout_channel": "cash"}
    body = _decide(client, _customer(), ben, {"amount": 500, "currency": "QAR"})
    assert body["outcome"] == "reject"
    rules = {r["rule"] for r in body["reasons"]}
    assert "beneficiary-listed" in rules and "do_not_send" in body["actions"]
    assert body["beneficiary_screening"]["sanctions_match"] is True
    assert body["beneficiary_screening"]["matches"][0]["sanctioned_name"] == "ABDUL RAHMAN YASIN"
    assert body["beneficiary_screening_id"]
    # stored on the decision and visible in the console
    d = client.get(f"/api/v1/decisions/{body['decision_id']}").json()
    assert d["beneficiary_screening_id"] == body["beneficiary_screening_id"]
    page = client.get(f"/review/{body['decision_id']}")
    assert "Beneficiary screening" in page.text and "ABDUL RAHMAN YASIN" in page.text


def test_beneficiary_identifier_match(client, sanctions_data_dir):
    row = "QA_NCTC,nctc.json,QL9,QLDi.900,Qatar NCTC domestic designation,individual,LISTED RECIPIENT,,,,,PHILIPPINES,,,,1980-05-05,1980,,Passport: P7654321A,Qatar domestic designation,,2025-01-01,2026-09-08,2026-09-08\n"
    (sanctions_data_dir / "combined" / f"combined_sanctions_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.csv").write_text(SAMPLE_COMBINED_CSV + row)
    from app.services.sanctions_loader import SanctionsLoader
    SanctionsLoader.clear_cache()
    ben = {"full_name": "Someone Else", "country": "PH", "id_type": "passport", "id_number": "P7654321A", "relationship": "x", "payout_channel": "x"}
    body = _decide(client, _customer(), ben)
    assert body["outcome"] == "reject"
    assert "beneficiary-identifier-match" in {r["rule"] for r in body["reasons"]}


def test_clean_beneficiary_does_not_fire(client):
    ben = {"full_name": "Rahul Sharma", "country": "PH", "relationship": "friend", "payout_channel": "bank"}
    body = _decide(client, _customer(), ben, {"amount": 500})
    assert body["outcome"] == "approve" and body["beneficiary_screening"]["sanctions_match"] is False


# ------------------------------------------------------------ country risk
def test_risk_lists_are_dated_and_used():
    lists = risk_lists()
    assert lists["fatf_call_for_action"]["as_of"] and set(lists["fatf_call_for_action"]["countries"]) == {"KP", "IR", "MM"}
    assert country_risk("IR") == "call_for_action"
    assert country_risk("YE") == "increased_monitoring"
    assert country_risk("PH") is None and country_risk(None) is None


def test_country_risk_rules(client):
    body = _decide(client, _customer(nationality="YE"), transfer={"amount": 100})
    assert "increased-monitoring-jurisdiction" in {r["rule"] for r in body["reasons"]} and body["outcome"] == "review"
    assert body["facts"]["customer.country_risk"] == "increased_monitoring"
    body = _decide(client, _customer(), {"full_name": "Kim Someone", "country": "KP", "relationship": "x", "payout_channel": "x"})
    assert "beneficiary-country-call-for-action" in {r["rule"] for r in body["reasons"]} and body["outcome"] == "reject"
    body = _decide(client, _customer(residence_country="IR"))
    assert "high-risk-nationality" in {r["rule"] for r in body["reasons"]}


# ----------------------------------------------------- internal watchlist
INTERNAL_CSV = (
    "name,aliases,type,dob,nationality,id_numbers,reason,reference\n"
    "Tariq Bin Salem,Tarek Salem;Tariq Salim,person,1988-03-03,YE,QID: 28812345678,Rejected 2025: source of funds unexplained,BL-1\n"
    "Golden Sands Trading,,entity,,,,QCB circular 2026-04,BL-2\n"
)


def test_internal_watchlist_upload_screens_and_fires_rule(client, sanctions_data_dir):
    assert client.get("/api/v1/lists/internal").json()["present"] is False
    r = client.post("/api/v1/lists/internal", files={"file": ("blacklist.csv", INTERNAL_CSV, "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["entries"] == 2 and r.json()["combined_file"].startswith("combined_sanctions_")
    assert client.get("/api/v1/lists/internal").json()["entries"] == 2
    lv = client.get("/api/v1/lists/current").json()
    assert lv["sources"].get("INTERNAL") == 2 and lv["sources"].get("UN") == 1

    # alias, QID and the rule
    s = client.post("/api/v1/aml/screen", json={"full_name": "Tarek Salem", "dob": "1988-03-03"}).json()
    assert s["sanctions_match"] and s["matches"][0]["source"] == "INTERNAL" and s["matches"][0]["match_type"] == "alias"
    s = client.post("/api/v1/aml/screen", json={"full_name": "Unknown Person", "id_numbers": ["28812345678"]}).json()
    assert s["matches"][0]["match_type"] == "identifier"
    body = _decide(client, _customer(full_name="Tariq Bin Salem", dob="1988-03-03", nationality="YE"))
    rules = {r["rule"] for r in body["reasons"]}
    assert "internal-watchlist-hit" in rules and body["outcome"] == "review"
    e = client.post("/api/v1/aml/screen", json={"full_name": "Golden Sands Trading", "entity_type": "entity"}).json()
    assert e["sanctions_match"] and e["matches"][0]["program"] == "INTERNAL"

    # replacing the list replaces, not appends
    r = client.post("/api/v1/lists/internal", files={"file": ("b2.csv", "name,type\nOnly One,person\n", "text/csv")})
    assert r.json()["entries"] == 1
    assert client.post("/api/v1/aml/screen", json={"full_name": "Tarek Salem"}).json()["sanctions_match"] is False
    assert client.post("/api/v1/lists/internal", files={"file": ("bad.csv", "foo,bar\n1,2\n", "text/csv")}).status_code == 422


def test_internal_watchlist_via_ui(client, sanctions_data_dir):
    r = client.post("/screen/internal-list", files={"file": ("bl.csv", INTERNAL_CSV, "text/csv")})
    assert r.status_code == 200 and "Internal watchlist replaced: 2 entries" in r.text
    assert "2 entries loaded" in client.get("/screen").text


# ------------------------------------------------------ OFAC consolidated
def test_ofac_consolidated_converter_reuses_sdn_parser(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, "scripts")
    import importlib
    mod = importlib.import_module("convert_ofac_cons_to_csv")
    raw = tmp_path / "raw"; raw.mkdir()
    (raw / "cons_prim.csv").write_text(
        '9001,"BANK EXAMPLE","-0- ","CAPTA","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","Executive Order 13846; Secondary sanctions risk."\n'
        '9002,"DOE, John","individual","NS-MBS","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","DOB 04 Jul 1970; POB Moscow, Russia; nationality Russia"\n')
    (raw / "cons_alt.csv").write_text('9001,101,"aka","EXAMPLE BANK PJSC","-0- "\n')
    (raw / "cons_add.csv").write_text('9001,201,"1 Main St","Moscow","Russia","-0- "\n')
    monkeypatch.setattr(mod, "RAW_DIR", raw)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    assert mod.main() == 0
    import pandas as pd
    df = pd.read_csv(tmp_path / "out" / "ofac_cons_sanctions_latest.csv", dtype=str, keep_default_na=False)
    assert set(df["source"]) == {"OFAC_CONS"} and len(df) == 2
    john = df[df["record_type"] == "individual"].iloc[0]
    assert john["dob_dates"] == "1970-07-04" and "NS-MBS" in john["program"]
    bank = df[df["record_type"] == "entity"].iloc[0]
    assert "EXAMPLE BANK PJSC" in bank["aliases"] and "CAPTA" in bank["program"]
