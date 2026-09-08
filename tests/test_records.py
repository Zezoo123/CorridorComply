"""Persistence, monitoring and alerts."""
import uuid

from tests.conftest import add_list_entry


def test_screening_is_persisted_with_list_version(client, db):
    r = client.post("/api/v1/aml/screen", json={"full_name": "Abdul Rahman Yasin", "dob": "1960-04-10", "nationality": "IQ"})
    assert r.status_code == 200
    sid = r.json()["screening_id"]
    assert sid
    row = client.get(f"/api/v1/screenings/{sid}").json()
    assert row["sanctions_match"] is True and row["channel"] == "api"
    assert row["list_version"].startswith("combined_sanctions_")
    assert row["matches"][0]["sanctioned_name"] == "ABDUL RAHMAN YASIN"
    listing = client.get("/api/v1/screenings").json()
    assert listing["count"] >= 1 and listing["screenings"][0]["id"] == sid
    lv = client.get("/api/v1/lists/current").json()
    assert lv["row_count"] == 5 and lv["checksum"] and lv["label"] == row["list_version"]


def test_batch_screening_is_persisted(client):
    r = client.post("/api/v1/aml/screen/batch", json={"items": [{"reference": "x", "full_name": "Bank Mellat", "entity_type": "entity"}]})
    assert r.status_code == 200
    assert r.json()["results"][0]["screening_id"]


def test_customers_upsert_and_list(client):
    payload = {"customers": [
        {"reference": "C-1", "full_name": "Jonathan Whitfield", "dob": "1979-02-03", "nationality": "GB"},
        {"reference": "C-2", "full_name": "Maria Santos", "dob": "1985-02-14", "nationality": "PH"},
    ]}
    r = client.post("/api/v1/customers", json=payload)
    assert r.status_code == 201
    out = {c["reference"]: c for c in r.json()["customers"]}
    assert out["C-1"]["last_screening"]["sanctions_match"] is False
    assert out["C-2"]["last_screening"]["sanctions_match"] is True

    # upsert changes the name, keeps one row
    r = client.post("/api/v1/customers", json={"customers": [{"reference": "C-1", "full_name": "Jonathan A. Whitfield"}], "screen_now": False})
    assert r.status_code == 201
    listing = client.get("/api/v1/customers").json()["customers"]
    assert len(listing) == 2 and {c["full_name"] for c in listing} == {"Jonathan A. Whitfield", "Maria Santos"}

    assert client.delete("/api/v1/customers/C-1").json()["monitored"] is False
    assert client.delete("/api/v1/customers/nope").status_code == 404
    assert len(client.get("/api/v1/customers?monitored=true").json()["customers"]) == 1


def test_rescreen_raises_alert_when_customer_newly_matches(client, sanctions_data_dir):
    client.post("/api/v1/customers", json={"customers": [
        {"reference": "C-1", "full_name": "Jonathan Whitfield", "dob": "1979-02-03", "nationality": "GB"},
        {"reference": "C-2", "full_name": "Rahul Sharma"},
    ]})
    # Nothing changed yet: customers already screened against this list version are skipped
    s = client.post("/api/v1/monitoring/rescreen").json()
    assert s["rescreened"] == 0 and s["skipped"] == 2 and s["alerts"] == 0
    assert client.get("/api/v1/alerts").json()["count"] == 0

    # A new list version adds Jonathan Whitfield
    add_list_entry(sanctions_data_dir, name="JONATHAN WHITFIELD", dob="1979-02-03", nationality="UNITED KINGDOM", dataid="777")
    s = client.post("/api/v1/monitoring/rescreen").json()
    assert s["rescreened"] == 2 and s["alerts"] == 1

    alerts = client.get("/api/v1/alerts").json()["alerts"]
    assert len(alerts) == 1
    a = alerts[0]
    assert a["kind"] == "new_hit" and a["customer"]["reference"] == "C-1"
    assert "JONATHAN WHITFIELD" in a["summary"]
    assert a["details"]["added"] == ["OFAC:777"]
    assert a["previous_screening_id"] and a["screening_id"] > a["previous_screening_id"]

    # Acknowledge
    r = client.post(f"/api/v1/alerts/{a['id']}/ack", json={"by": "mlro", "note": "false positive, different person"})
    assert r.status_code == 200 and r.json()["status"] == "acknowledged"
    assert client.get("/api/v1/alerts").json()["count"] == 0
    assert client.get("/api/v1/alerts?status=all").json()["count"] == 1
    assert client.post("/api/v1/alerts/9999/ack", json={}).status_code == 404

    # Same version again: nothing to do
    s = client.post("/api/v1/monitoring/rescreen").json()
    assert s["rescreened"] == 0
    # force re-screens without creating duplicate alerts (no change)
    s = client.post("/api/v1/monitoring/rescreen?force=true").json()
    assert s["rescreened"] == 2 and s["alerts"] == 0


def test_rescreen_new_match_and_hit_cleared(client, sanctions_data_dir):
    client.post("/api/v1/customers", json={"customers": [{"reference": "M", "full_name": "Maria Santos", "dob": "1985-02-14"}]})
    add_list_entry(sanctions_data_dir, name="MARIA DEL CARMEN SANTOS", aliases="MARIA SANTOS", dob="1985-02-14", dataid="555")
    s = client.post("/api/v1/monitoring/rescreen").json()
    assert s["alerts"] == 1
    a = client.get("/api/v1/alerts").json()["alerts"][0]
    assert a["kind"] == "new_match" and a["details"]["added"] == ["OFAC:555"]

    # Next version: the customer's own name is changed so they no longer match anything
    client.post("/api/v1/customers", json={"customers": [{"reference": "M", "full_name": "Marisol Quintero"}], "screen_now": False})
    add_list_entry(sanctions_data_dir, name="SOMEONE ELSE", dataid="556")
    s = client.post("/api/v1/monitoring/rescreen").json()
    kinds = [x["kind"] for x in client.get("/api/v1/alerts").json()["alerts"]]
    assert "hit_cleared" in kinds


def test_tenant_settings_and_webhook(client, sanctions_data_dir, monkeypatch):
    r = client.put("/api/v1/tenant", json={"webhook_url": "https://example.test/hook", "name": "Dev tenant"})
    assert r.json()["webhook_url"] == "https://example.test/hook"
    assert client.get("/api/v1/tenant").json()["name"] == "Dev tenant"

    sent = {}
    class FakeResp:
        status_code = 200
    def fake_post(url, json=None, timeout=None):
        sent["url"] = url; sent["json"] = json; return FakeResp()
    import requests
    monkeypatch.setattr(requests, "post", fake_post)

    client.post("/api/v1/customers", json={"customers": [{"reference": "W", "full_name": "Rahul Sharma"}]})
    add_list_entry(sanctions_data_dir, name="RAHUL SHARMA", dataid="888")
    client.post("/api/v1/monitoring/rescreen")
    assert sent["url"] == "https://example.test/hook"
    assert sent["json"]["alerts"][0]["kind"] == "new_hit"
    assert sent["json"]["tenant"] == "dev"


def test_db_backed_api_keys(client, db, monkeypatch):
    from app import auth
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("API_KEYS_FILE", raising=False)
    key = auth.create_key("acme-exchange", label="laptop")
    assert key.startswith("cc_")
    try:
        assert client.post("/api/v1/aml/screen", json={"full_name": "Rahul Sharma"}).status_code == 401
        r = client.post("/api/v1/aml/screen", json={"full_name": "Rahul Sharma"}, headers={"X-API-Key": key})
        assert r.status_code == 200
        # screenings are scoped to the key's tenant
        assert client.get("/api/v1/screenings", headers={"X-API-Key": key}).json()["count"] == 1
        assert auth.revoke_key(key[:10]) == 1
        assert client.post("/api/v1/aml/screen", json={"full_name": "Rahul Sharma"}, headers={"X-API-Key": key}).status_code == 401
    finally:
        auth.reset_keys()


def test_monitoring_cli(client, sanctions_data_dir, capsys):
    from app import monitoring
    client.post("/api/v1/customers", json={"customers": [{"reference": "K", "full_name": "Rahul Sharma"}]})
    add_list_entry(sanctions_data_dir, name="RAHUL SHARMA", dataid="889")
    assert monitoring.main(["rescreen"]) == 0
    out = capsys.readouterr().out
    assert '"alerts": 1' in out
    assert monitoring.main([]) == 2


def test_web_upload_can_enrol_customers_and_shows_alerts(client, sanctions_data_dir):
    csv = "customer_id,full_name,date_of_birth,nationality\nU-1,Rahul Sharma,1988-11-30,IN\nU-2,Jonathan Whitfield,1979-02-03,GB\n"
    r = client.post("/screen", data={"monitor": "1"}, files={"file": ("c.csv", csv, "text/csv")})
    assert r.status_code == 200 and "ongoing monitoring" in r.text
    assert client.get("/alerts").status_code == 200
    add_list_entry(sanctions_data_dir, name="RAHUL SHARMA", dob="1988-11-30", nationality="INDIA", dataid="890")
    r = client.post("/alerts/rescreen", follow_redirects=True)
    assert r.status_code == 200 and "new hit" in r.text and "Rahul Sharma" in r.text
    assert 'class="pill high">1</span>' in r.text  # nav badge
    import re
    alert_id = int(re.search(r'action="/alerts/(\d+)/ack"', r.text).group(1))
    r = client.post(f"/alerts/{alert_id}/ack", data={"note": "checked"}, follow_redirects=True)
    assert "No open alerts" in r.text
