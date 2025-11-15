from pydantic import BaseModel, Field
from typing import List, Optional
from .risk import RiskLevel

class MatchResult(BaseModel):
    sanctioned_name: str
    source: str
    similarity: int = Field(..., ge=0, le=100, description="Similarity score 0-100")
    confidence: str = Field(..., description="Confidence level: high, medium, or low")
    dob: Optional[str] = None
    dob_match: Optional[bool] = Field(None, description="Whether DOB matches if provided")
    country: Optional[str] = None
    country_match: Optional[bool] = Field(None, description="Whether country matches if provided")

class AMLScreenRequest(BaseModel):
    full_name: str = Field(..., example="Ahmed Ali")
    dob: str = Field(..., example="1989-03-12")
    nationality: str = Field(..., example="QA")

class AMLScreenResponse(BaseModel):
    sanctions_match: bool = False
    pep_match: bool = False
    risk_score: int = Field(..., ge=0, le=100, example=5)
    risk_level: RiskLevel = RiskLevel.LOW
    details: List[str] = Field(default_factory=list)
    matches: List[MatchResult] = Field(default_factory=list)
