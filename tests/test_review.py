"""Review console and dispositions."""
import re

from app.corridor import engine as corridor_engine


def _decision(client, name="Abdul Rahman Yasin", dob="1960-04-10", nat="IQ", reference="R-1"):
    corridor_engine.reset_registry()
    payload = {"corridor": "QA-PH", "customer": {
        "full_name": name, "dob": dob, "place_of_birth": "x", "nationality": nat, "document_type": "passport",
        "document_number": "A1234567", "document_expiry": "2030-01-01", "mobile": "x", "address_qatar": "x",
        "profession": "x", "employer_sponsor": "x", "purpose": "family support", "is_resident": False, "reference": reference}}
    r = client.post("/api/v1/decision", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_pending_queue_and_api_disposition(client):
    hit = _decision(client)
    clean = _decision(client, name="Jonathan Whitfield", dob="1979-02-03", nat="GB", reference="R-2")
    assert hit["outcome"] == "reject" and clean["outcome"] == "approve"

    pending = client.get("/api/v1/decisions?pending=true").json()
    assert [d["id"] for d in pending["decisions"]] == [hit["decision_id"]]

    # reason and name are mandatory
    r = client.post(f"/api/v1/decisions/{hit['decision_id']}/disposition", json={"outcome": "approved", "reason": "", "by": "x"})
    assert r.status_code == 422
    r = client.post(f"/api/v1/decisions/{hit['decision_id']}/disposition",
                    json={"outcome": "rejected", "reason": "Exact DOB match on the UN list; MLRO informed, STR filed", "by": "Fatima Al-Kuwari"})
    assert r.status_code == 200
    body = r.json()
    assert body["disposition"] == "rejected" and body["disposition_by"] == "Fatima Al-Kuwari"
    assert body["hours_to_close"] is not None and body["hours_to_close"] >= 0

    assert client.get("/api/v1/decisions?pending=true").json()["count"] == 0
    closed = client.get("/api/v1/decisions?pending=false").json()
    assert closed["count"] == 1 and closed["decisions"][0]["disposition_reason"].startswith("Exact DOB")
    assert client.post("/api/v1/decisions/9999/disposition", json={"outcome": "approved", "reason": "abc", "by": "me"}).status_code == 404


def test_evidence_bundle(client):
    hit = _decision(client, reference="EV-1")
    client.post(f"/api/v1/decisions/{hit['decision_id']}/disposition", json={"outcome": "escalated", "reason": "needs MLRO", "by": "Reviewer"})
    b = client.get("/api/v1/customers/EV-1/evidence").json()
    assert b["customer"]["reference"] == "EV-1"
    assert len(b["screenings"]) == 1 and len(b["decisions"]) == 1 and b["alerts"] == []
    assert b["decisions"][0]["disposition"] == "escalated"
    assert b["list_versions"] and b["list_versions"][0].startswith("combined_sanctions_")
    assert client.get("/api/v1/customers/nope/evidence").status_code == 404


def test_review_console_pages(client):
    hit = _decision(client, reference="UI-1")
    r = client.get("/review")
    assert r.status_code == 200 and "Abdul Rahman Yasin" in r.text and 'class="pill medium">1</span>' in r.text
    page = client.get(f"/review/{hit['decision_id']}")
    assert page.status_code == 200
    assert "Record your disposition" in page.text
    assert "Listed person: UNSC or Qatar NCTC designation confirmed" in page.text   # rule title
    assert "ABDUL RAHMAN YASIN" in page.text                                        # screening match
    assert "QCB AML/CFT Instructions 10.4" in page.text                             # basis shown to reviewer
    assert "Export evidence bundle" in page.text

    # missing reason is rejected with the form re-rendered
    r = client.post(f"/review/{hit['decision_id']}", data={"outcome": "approved", "reason": "", "by": "A"})
    assert r.status_code == 200 and "reason is required" in r.text

    r = client.post(f"/review/{hit['decision_id']}", data={"outcome": "approved", "reason": "Verified in person; namesake", "by": "Omar K"}, follow_redirects=True)
    assert r.status_code == 200 and "Disposition: approved" in r.text and "Omar K" in r.text
    assert "Record your disposition" not in r.text
    assert "Nothing to review" in client.get("/review").text
    assert "Omar K" in client.get("/review?show=closed").text
    assert client.get("/review/9999").status_code == 404
