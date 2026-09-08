"""Liveness provider interface."""
from PIL import Image

from app.services import liveness
from app.services.risk_engine import RiskEngine


def test_null_provider_reports_not_checked(monkeypatch):
    monkeypatch.delenv("LIVENESS_PROVIDER", raising=False)
    r = liveness.get_provider().check(Image.new("RGB", (4, 4)))
    assert r.checked is False and r.live is None and r.provider == "none"
    assert r.to_dict()["checked"] is False


def test_http_provider_parses_and_survives_failure(monkeypatch):
    calls = {}
    class Resp:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        def json(self): return self._p
    def fake_post(url, json=None, headers=None, timeout=None):
        calls["url"], calls["headers"], calls["has_image"] = url, headers, bool(json.get("image"))
        return Resp({"live": True, "score": 0.93})
    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setenv("LIVENESS_PROVIDER", "http")
    monkeypatch.setenv("LIVENESS_URL", "https://vendor.test/liveness")
    monkeypatch.setenv("LIVENESS_API_KEY", "k")
    r = liveness.get_provider().check(Image.new("RGB", (4, 4)))
    assert r.checked and r.live is True and r.score == 0.93 and r.provider == "http"
    assert calls["url"] == "https://vendor.test/liveness" and calls["headers"]["Authorization"] == "Bearer k" and calls["has_image"]

    def failing_post(*a, **k): raise RuntimeError("down")
    monkeypatch.setattr(requests, "post", failing_post)
    r = liveness.get_provider().check(Image.new("RGB", (4, 4)))
    assert r.checked and r.live is None and "down" in r.error


def test_http_without_url_falls_back_to_null(monkeypatch):
    monkeypatch.setenv("LIVENESS_PROVIDER", "http")
    monkeypatch.delenv("LIVENESS_URL", raising=False)
    assert isinstance(liveness.get_provider(), liveness.NullProvider)


def test_risk_engine_scores_only_a_failed_liveness_check():
    assert RiskEngine.calculate_kyc_risk_score(liveness=None)["risk_score"] == 0
    assert RiskEngine.calculate_kyc_risk_score(liveness=True)["risk_score"] == 0
    r = RiskEngine.calculate_kyc_risk_score(liveness=False)
    assert r["risk_score"] == 35 and "Liveness" in r["risk_factors"][0]["description"]
