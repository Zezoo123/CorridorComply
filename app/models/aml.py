from pydantic import BaseModel, Field
from typing import List
from .risk import RiskLevel

class AMLScreenRequest(BaseModel):
    full_name: str = Field(..., example="Ahmed Ali")
    dob: str = Field(..., example="1989-03-12")
    nationality: str = Field(..., example="QA")
    # later: we'll add address, IDs, etc.

class AMLScreenResponse(BaseModel):
    sanctions_match: bool = False
    pep_match: bool = False
    risk_score: int = Field(..., ge=0, le=100, example=5)
    risk_level: RiskLevel = RiskLevel.LOW
    details: List[str] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "sanctions_match": False,
                "pep_match": False,
                "risk_score": 5,
                "risk_level": "low",
                "details": [
                    "No sanctions match found (stub)",
                    "No PEP match found (stub)",
                ],
            }
        }
