from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from .enums import RiskLevel
from .aml import AMLScreenRequest, AMLScreenResponse, MatchResult
from .kyc import KYCRequest, KYCResponse, DocumentData

class CombinedRiskRequest(BaseModel):
    """Request for combined risk assessment.
    
    This requires both AML and KYC data to be provided, and will always perform
    fresh AML and KYC checks as part of the combined risk assessment.
    """
    aml_data: AMLScreenRequest = Field(..., description="AML screening data")
    kyc_data: KYCRequest = Field(..., description="KYC verification data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "aml_data": {
                    "full_name": "John Doe",
                    "dob": "1990-01-01",
                    "nationality": "US"
                },
                "kyc_data": {
                    "document_data": {
                        "document_type": "passport",
                        "document_number": "P1234567",
                        "expiry_date": "2030-12-31",
                        "issuing_country": "US",
                        "first_name": "John",
                        "last_name": "Doe",
                        "date_of_birth": "1990-01-01",
                        "nationality": "US",
                        "address": {
                            "street": "123 Main St",
                            "city": "New York",
                            "country": "US"
                        }
                    },
                    "document_image_base64": "base64_encoded_document_image",
                    "selfie_image_base64": "base64_encoded_selfie_image"
                }
            }
        }

class CombinedRiskResponse(BaseModel):
    """Combined risk assessment response"""
    request_id: str = Field(..., example="550e8400-e29b-41d4-a716-446655440000")
    combined_risk_score: int = Field(..., ge=0, le=100, example=65)
    combined_risk_level: RiskLevel = Field(..., example=RiskLevel.MEDIUM)
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)
    aml_risk_score: Optional[int] = Field(None, ge=0, le=100, example=50)
    aml_risk_level: Optional[RiskLevel] = Field(None, example=RiskLevel.MEDIUM)
    kyc_risk_score: Optional[int] = Field(None, ge=0, le=100, example=30)
    kyc_risk_level: Optional[RiskLevel] = Field(None, example=RiskLevel.LOW)
    details: List[str] = Field(default_factory=list)
    aml_details: Optional[Dict[str, Any]] = Field(None)
    kyc_details: Optional[Dict[str, Any]] = Field(None)

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "combined_risk_score": 65,
                "combined_risk_level": "medium",
                "risk_factors": [
                    {"type": "kyc_document_issue", "severity": "medium", "description": "Document expiring soon"},
                    {"type": "aml_watchlist", "severity": "low", "description": "Name match on sanctions list"}
                ],
                "aml_risk_score": 50,
                "aml_risk_level": "medium",
                "kyc_risk_score": 30,
                "kyc_risk_level": "low",
                "details": [
                    "Document verification successful",
                    "Face match: 95%"
                ],
                "aml_details": {
                    "sanctions_match": False,
                    "pep_match": True,
                    "matches": [
                        {
                            "sanctioned_name": "John Doe",
                            "source": "PEP Database",
                            "similarity": 85.5,
                            "confidence": "high"
                        }
                    ]
                },
                "kyc_details": {
                    "document_verified": True,
                    "face_match": True,
                    "liveness_detected": True,
                    "ocr_quality": 0.98
                }
            }
        }
