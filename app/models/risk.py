from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IdentityData(BaseModel):
    """Common identity fields shared by AML and KYC"""
    full_name: str = Field(..., example="Ahmed Ali")
    dob: str = Field(..., example="1989-03-12")
    nationality: str = Field(..., example="QA")


class AMLInputData(IdentityData):
    """AML screening input data - uses common identity fields"""
    pass


class KYCInputData(IdentityData):
    """KYC verification input data - extends identity with document-specific fields"""
    document_type: str = Field(..., example="passport")
    document_number: str = Field(..., example="P1234567")
    face_match_score: Optional[float] = Field(None, ge=0.0, le=1.0, example=0.85)
    face_match_result: Optional[bool] = Field(None, example=True)
    ocr_quality: Optional[float] = Field(None, ge=0.0, le=1.0, example=0.90)
    document_expired: bool = Field(False, example=False)
    document_expiring_soon: bool = Field(False, example=False)
    missing_fields: Optional[List[str]] = Field(None, example=[])
    data_quality_issues: Optional[List[str]] = Field(None, example=[])


class PreCalculatedRisk(BaseModel):
    """Pre-calculated risk data from a previous check"""
    risk_score: int = Field(..., ge=0, le=100, example=45)
    risk_level: RiskLevel = Field(..., example=RiskLevel.MEDIUM)
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)


class CombinedRiskRequest(BaseModel):
    """Request for combined risk assessment"""
    aml_data: Optional[AMLInputData] = Field(None, description="AML screening data")
    kyc_data: Optional[KYCInputData] = Field(None, description="KYC verification data")
    aml_risk: Optional[PreCalculatedRisk] = Field(None, description="Pre-calculated AML risk (if already computed)")
    kyc_risk: Optional[PreCalculatedRisk] = Field(None, description="Pre-calculated KYC risk (if already computed)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "aml_data": {
                    "full_name": "Ahmed Ali",
                    "dob": "1989-03-12",
                    "nationality": "QA"
                },
                "kyc_data": {
                    "full_name": "Ahmed Ali",
                    "dob": "1989-03-12",
                    "nationality": "QA",
                    "document_type": "passport",
                    "document_number": "P1234567"
                }
            }
        }


class CombinedRiskResponse(BaseModel):
    """Combined risk assessment response"""
    combined_risk_score: int = Field(..., ge=0, le=100, example=65)
    combined_risk_level: RiskLevel = Field(..., example=RiskLevel.MEDIUM)
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)
    aml_risk_score: Optional[int] = Field(None, ge=0, le=100, example=50)
    aml_risk_level: Optional[RiskLevel] = Field(None, example=RiskLevel.MEDIUM)
    kyc_risk_score: Optional[int] = Field(None, ge=0, le=100, example=30)
    kyc_risk_level: Optional[RiskLevel] = Field(None, example=RiskLevel.LOW)
    details: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "combined_risk_score": 65,
                "combined_risk_level": "medium",
                "aml_risk_score": 50,
                "aml_risk_level": "medium",
                "kyc_risk_score": 30,
                "kyc_risk_level": "low",
                "details": [
                    "AML: Sanctions match found",
                    "KYC: Document format valid"
                ],
                "risk_factors": [
                    {
                        "type": "aml_sanctions",
                        "severity": "high",
                        "description": "Sanctions list match found"
                    }
                ]
            }
        }
