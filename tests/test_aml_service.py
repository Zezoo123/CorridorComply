"""
Unit tests for AML screening (AMLService + SanctionsLoader integration).
"""
import pytest

from app.services.aml_service import AMLService
from app.services.sanctions_loader import SanctionsLoader


def run(coro):
    import asyncio
    return asyncio.run(coro)


def test_loader_caches_between_calls(sanctions_data_dir):
    first = SanctionsLoader.load()
    assert SanctionsLoader._cache is not None, "cache must be populated after the first load"
    second = SanctionsLoader.load()
    assert first is second


def test_exact_name_is_a_high_confidence_match(sanctions_data_dir):
    result = run(AMLService.screen("t", "Abdul Rahman Yasin", "1960-04-10", "IQ"))
    assert result["sanctions_match"] is True
    names = [m["sanctioned_name"] for m in result["matches"]]
    assert "ABDUL RAHMAN YASIN" in names
    assert result["risk_level"].value == "high"


def test_word_order_does_not_matter(sanctions_data_dir):
    result = run(AMLService.screen("t", "Yasin Abdul Rahman", "", ""))
    assert result["sanctions_match"] is True


def test_clean_name_has_no_match(sanctions_data_dir):
    result = run(AMLService.screen("t", "Jonathan Whitfield", "1990-01-01", "GB"))
    assert result["sanctions_match"] is False
    assert result["risk_score"] == 0
    assert result["details"] == ["No matches found"]


def test_common_name_collision_is_reported_with_similarity(sanctions_data_dir):
    result = run(AMLService.screen("t", "Maria Santos", "1999-09-09", "PH"))
    assert result["sanctions_match"] is True
    match = result["matches"][0]
    assert 0 <= match["similarity"] <= 100
    assert match["confidence"] in {"high", "medium", "low"}


def test_response_shape(sanctions_data_dir):
    result = run(AMLService.screen("t", "Bank Mellat", "", ""))
    for key in ("request_id", "sanctions_match", "pep_match", "risk_score", "risk_level", "details", "matches"):
        assert key in result
    assert result["pep_match"] is False  # PEP screening not implemented yet
