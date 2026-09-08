"""
API tests using FastAPI's TestClient (no running server required).
"""
import base64
import uuid
from io import BytesIO

import pytest
from PIL import Image

from tests.conftest import read_audit_entries


def tiny_png_b64() -> str:
    img = Image.new("RGB", (1, 1), color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def kyc_payload(**overrides):
    payload = {
        "document_data": {
            "document_type": "passport",
            "document_number": "P1234567",
            "expiry_date": "2030-12-31",
            "issuing_country": "PH",
            "first_name": "Maria",
            "last_name": "Santos",
            "date_of_birth": "1985-02-14",
            "nationality": "PH",
            "address": {"city": "Doha", "country": "QA"},
        },
        "document_image_base64": tiny_png_b64(),
        "selfie_image_base64": tiny_png_b64(),
    }
    payload.update(overrides)
    return payload


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}
    assert r.headers["X-Request-ID"].startswith("req_")


def test_request_id_is_echoed_when_supplied(client):
    r = client.get("/health", headers={"X-Request-ID": "my-trace-123"})
    assert r.headers["X-Request-ID"] == "my-trace-123"


def test_aml_screen_no_match(client):
    r = client.post("/api/v1/aml/screen", json={"full_name": "Jonathan Whitfield", "dob": "1990-01-01", "nationality": "GB"})
    assert r.status_code == 200
    body = r.json()
    assert body["sanctions_match"] is False
    assert body["risk_level"] == "low"
    assert body["matches"] == []


def test_aml_screen_match_and_audit_entry(client):
    rid = f"audit-aml-{uuid.uuid4().hex[:8]}"  # the audit log persists across runs
    r = client.post(
        "/api/v1/aml/screen",
        json={"full_name": "Mohammad Reza Naqdi", "dob": "1953-03-11", "nationality": "IR"},
        headers={"X-Request-ID": rid},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["request_id"] == rid
    assert body["sanctions_match"] is True
    assert body["risk_level"] == "high"

    entries = [e for e in read_audit_entries() if e.get("request_id") == rid]
    assert len(entries) == 1, "exactly one audit event per screening"
    entry = entries[0]
    assert entry["event_type"] == "aml_screening"
    assert entry["status"] == "success"
    assert entry["request_payload"]["full_name"] == "Mohammad Reza Naqdi"
    assert entry["method"] == "POST"


def test_aml_screen_validation_error(client):
    r = client.post("/api/v1/aml/screen", json={"full_name": "x"})
    assert r.status_code == 422


def test_kyc_rejects_invalid_document_image(client):
    r = client.post("/api/v1/kyc/verify", json=kyc_payload(document_image_base64="not-base64!!"))
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "Invalid document image"


def test_kyc_rejects_invalid_selfie_image(client):
    r = client.post("/api/v1/kyc/verify", json=kyc_payload(selfie_image_base64="@@@"))
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "Invalid selfie image"


def test_unknown_route_is_404(client):
    assert client.get("/api/v1/nope").status_code == 404


@pytest.mark.slow
def test_kyc_verify_end_to_end_with_tiny_images(client):
    """Loads OCR and face-matching models; the 1x1 images fail gracefully."""
    rid = f"audit-kyc-{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/kyc/verify", json=kyc_payload(), headers={"X-Request-ID": rid})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["verification_result"]["document_verified"] is False
    assert body["verification_result"]["face_match"] is False
    assert body["risk_level"] == "high"
    entries = [e for e in read_audit_entries() if e.get("request_id") == rid]
    assert len(entries) == 1
    assert entries[0]["request_payload"]["document_image_base64"].startswith("<base64_image_data")


@pytest.mark.slow
def test_combined_risk_end_to_end(client):
    payload = {
        "aml_data": {"full_name": "Jonathan Whitfield", "dob": "1990-01-01", "nationality": "GB"},
        "kyc_data": kyc_payload(),
    }
    rid = f"audit-risk-{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/risk/combined", json=payload, headers={"X-Request-ID": rid})
    assert r.status_code == 200
    body = r.json()
    assert body["aml_risk_level"] == "low"
    assert body["kyc_risk_level"] == "high"
    assert 0 <= body["combined_risk_score"] <= 100
    entries = [e for e in read_audit_entries() if e.get("request_id") == rid]
    assert any(e["event_type"] == "combined_risk_assessment" for e in entries)
