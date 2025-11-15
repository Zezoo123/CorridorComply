from pydantic import BaseModel, Field
from typing import List, Optional
from .risk import RiskLevel

class KYCRequest(BaseModel):
    full_name: str = Field(..., example="Juan Dela Cruz")
    dob: str = Field(..., example="1990-01-01")  # later: use date type
    nationality: str = Field(..., example="PH")
    document_type: str = Field(..., example="passport")
    document_number: str = Field(..., example="P1234567")
    # Later we'll accept base64 images or file uploads for doc/selfie

class KYCResponse(BaseModel):
    status: str = Field(..., example="pass")  # "pass" | "fail" | "review"
    risk_score: int = Field(..., ge=0, le=100, example=15)
    risk_level: RiskLevel = RiskLevel.LOW
    details: List[str] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "status": "pass",
                "risk_score": 15,
                "risk_level": "low",
                "details": [
                    "Document format valid",
                    "Basic checks passed (stub)",
                ],
            }
        }
