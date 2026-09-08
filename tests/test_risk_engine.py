"""
Unit tests for the unified RiskEngine.
"""
from app.services.risk_engine import RiskEngine
from app.models.risk import RiskLevel


def test_risk_level_thresholds():
    assert RiskEngine.calculate_risk_level(0) == RiskLevel.LOW
    assert RiskEngine.calculate_risk_level(39) == RiskLevel.LOW
    assert RiskEngine.calculate_risk_level(40) == RiskLevel.MEDIUM
    assert RiskEngine.calculate_risk_level(69) == RiskLevel.MEDIUM
    assert RiskEngine.calculate_risk_level(70) == RiskLevel.HIGH
    assert RiskEngine.calculate_risk_level(100) == RiskLevel.HIGH


def test_confidence_levels():
    assert RiskEngine.get_confidence_level(100) == "high"
    assert RiskEngine.get_confidence_level(95) == "high"
    assert RiskEngine.get_confidence_level(90) == "medium"
    assert RiskEngine.get_confidence_level(84) == "low"


def test_aml_score_no_match():
    r = RiskEngine.calculate_aml_risk_score(matches=[], has_sanctions_match=False)
    assert r["risk_score"] == 0
    assert r["risk_level"] == RiskLevel.LOW
    assert r["risk_factors"] == []


def test_aml_score_high_confidence_match_is_high_risk():
    matches = [{"similarity": 100, "dob_match": True, "country_match": True}]
    r = RiskEngine.calculate_aml_risk_score(matches=matches, has_sanctions_match=True)
    assert r["risk_score"] == 95
    assert r["risk_level"] == RiskLevel.HIGH


def test_aml_score_low_confidence_match_is_medium_risk():
    matches = [{"similarity": 85, "dob_match": None, "country_match": None}]
    r = RiskEngine.calculate_aml_risk_score(matches=matches, has_sanctions_match=True)
    assert r["risk_score"] == 65
    assert r["risk_level"] == RiskLevel.MEDIUM


def test_aml_score_is_capped_at_100():
    matches = [{"similarity": 100, "dob_match": True, "country_match": True}] * 5
    r = RiskEngine.calculate_aml_risk_score(matches=matches, has_sanctions_match=True)
    assert r["risk_score"] == 100


def test_kyc_score_face_mismatch_and_expiry():
    r = RiskEngine.calculate_kyc_risk_score(face_match_result=False, document_expired=True)
    assert r["risk_score"] == 65
    assert r["risk_level"] == RiskLevel.MEDIUM


def test_combined_score_weights_aml_60_kyc_40():
    aml = RiskEngine.calculate_aml_risk_score(matches=[{"similarity": 100}], has_sanctions_match=True)  # 80
    kyc = RiskEngine.calculate_kyc_risk_score(face_match_result=False)  # 35
    r = RiskEngine.calculate_combined_risk_score(aml, kyc)
    assert r["risk_score"] == int(80 * 0.6 + 35 * 0.4)
    assert r["risk_level"] == RiskLevel.MEDIUM


def test_combined_score_single_source_uses_it_directly():
    aml = RiskEngine.calculate_aml_risk_score(matches=[{"similarity": 100}], has_sanctions_match=True)
    r = RiskEngine.calculate_combined_risk_score(aml_risk_data=aml, kyc_risk_data=None)
    assert r["risk_score"] == aml["risk_score"]
