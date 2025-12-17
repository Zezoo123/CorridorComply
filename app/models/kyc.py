from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from .enums import RiskLevel, DocumentType, VerificationStatus

class DocumentData(BaseModel):
    document_type: str
    document_number: str
    expiry_date: str
    issue_date: Optional[str] = None
    issuing_country: str
    first_name: str
    last_name: str
    date_of_birth: str
    nationality: str
    address: Dict[str, Any]

class KYCRequest(BaseModel):
    document_data: DocumentData
    document_image_base64: str
    selfie_image_base64: str
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# RiskLevel is now imported from .enums

class KYCResponse(BaseModel):
    request_id: str
    status: str
    risk_score: Optional[float] = Field(None, ge=0, le=100)
    risk_level: Optional[RiskLevel] = None
    verification_result: Optional[Dict[str, Any]] = None
    timestamp: str
    error: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "req_123456",
                "status": "success",
                "risk_score": 15,
                "risk_level": "low",
                "verification_result": {
                    "document_verified": True,
                    "face_match": True,
                    "liveness_detected": True
                },
                "timestamp": "2023-04-01T12:00:00.000000",
                "error": None
            }
        }

class KYCDocumentVerification(BaseModel):
    status: str
    risk_score: float
    risk_level: RiskLevel
    details: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "status": "pass",
                "risk_score": 15,
                "risk_level": "low",
                "details": [
                    "Document format valid",
                    "Basic checks passed",
                ],
            }
        }

class KYCMatchResult(BaseModel):
    matched: bool
    confidence: float
    details: Dict[str, Any]

class KYCFaceMatch(BaseModel):
    status: str
    score: float
    threshold: float
    is_match: bool