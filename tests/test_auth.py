"""API-key authentication tests."""
import json

import pytest

from app import auth


@pytest.fixture
def keyed_client(client, monkeypatch, tmp_path):
    keys_file = tmp_path / "keys.json"
    keys_file.write_text(json.dumps({"acme-exchange": "cc_test_key_1"}))
    monkeypatch.setenv("API_KEYS", "doha-remit:cc_test_key_2")
    monkeypatch.setenv("API_KEYS_FILE", str(keys_file))
    auth.reset_keys()
    yield client
    auth.reset_keys()


def test_open_when_no_keys_configured(client, monkeypatch):
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("API_KEYS_FILE", raising=False)
    auth.reset_keys()
    r = client.post("/api/v1/aml/screen", json={"full_name": "Jonathan Whitfield"})
    assert r.status_code == 200
    auth.reset_keys()


def test_missing_key_is_401(keyed_client):
    r = keyed_client.post("/api/v1/aml/screen", json={"full_name": "Jonathan Whitfield"})
    assert r.status_code == 401
    assert "X-API-Key" in r.json()["detail"]


def test_wrong_key_is_401(keyed_client):
    r = keyed_client.post("/api/v1/aml/screen", json={"full_name": "Jonathan Whitfield"}, headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_valid_keys_from_env_and_file(keyed_client):
    for key in ("cc_test_key_1", "cc_test_key_2"):
        r = keyed_client.post("/api/v1/aml/screen", json={"full_name": "Jonathan Whitfield"}, headers={"X-API-Key": key})
        assert r.status_code == 200


def test_tenant_recorded_in_audit_log(keyed_client):
    import uuid
    from tests.conftest import read_audit_entries
    rid = f"tenant-{uuid.uuid4().hex[:8]}"
    r = keyed_client.post("/api/v1/aml/screen", json={"full_name": "Jonathan Whitfield"},
                          headers={"X-API-Key": "cc_test_key_1", "X-Request-ID": rid})
    assert r.status_code == 200
    entry = next(e for e in read_audit_entries() if e.get("request_id") == rid)
    assert entry["tenant"] == "acme-exchange"


def test_health_and_ui_do_not_require_a_key(keyed_client):
    assert keyed_client.get("/health").status_code == 200
    assert keyed_client.get("/screen").status_code == 200


def test_new_key_format():
    k = auth.new_key()
    assert k.startswith("cc_") and len(k) > 30
