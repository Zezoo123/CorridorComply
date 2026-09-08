from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from .enums import RiskLevel

EntityType = Literal["person", "entity", "vessel", "any"]


class MatchResult(BaseModel):
    sanctioned_name: str = Field(..., description="Primary name on the list")
    matched_name: Optional[str] = Field(None, description="The name or alias that produced the score")
    match_type: Optional[str] = Field(None, description="'name' or 'alias'")
    source: str
    dataid: Optional[str] = None
    record_type: Optional[str] = None
    program: Optional[str] = None
    listed_on: Optional[str] = None
    similarity: float = Field(..., ge=0.0, le=100.0, description="Similarity score 0-100")
    confidence: str = Field(..., description="Confidence level: high, medium, or low")
    aliases: List[str] = Field(default_factory=list)
    dob: Optional[List[str]] = Field(None, description="Dates or years of birth on the list entry")
    dob_agreement: Optional[str] = Field(None, description="exact | year | mismatch | unknown")
    dob_match: Optional[bool] = Field(None, description="Whether DOB agrees (None if unknown)")
    country: Optional[str] = None
    country_match: Optional[bool] = Field(None, description="Whether nationality agrees (None if unknown)")


class AMLScreenRequest(BaseModel):
    full_name: str = Field(..., min_length=2, json_schema_extra={"example": "Ahmed Ali"})
    dob: Optional[str] = Field(None, json_schema_extra={"example": "1989-03-12"}, description="YYYY-MM-DD")
    nationality: Optional[str] = Field(None, json_schema_extra={"example": "QA"}, description="ISO code or country name")
    entity_type: EntityType = Field("person", description="What is being screened")


class AMLScreenResponse(BaseModel):
    request_id: str
    sanctions_match: bool = False
    pep_match: bool = False
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: RiskLevel = RiskLevel.LOW
    details: List[str] = Field(default_factory=list)
    matches: List[MatchResult] = Field(default_factory=list)
    list_version: Optional[str] = Field(None, description="Identifier of the list file screened against")
    screening_id: Optional[int] = Field(None, description="Persistent evidence record id")
    name_flags: List[str] = Field(default_factory=list, description="single_name, patronymic, compound_surname, suffix")
    screened_variants: List[str] = Field(default_factory=list, description="Name forms actually screened")


class AMLBatchItem(AMLScreenRequest):
    reference: Optional[str] = Field(None, description="Caller's own identifier for this row")


class AMLBatchRequest(BaseModel):
    items: List[AMLBatchItem] = Field(..., min_length=1, max_length=5000)


class AMLBatchResult(AMLScreenResponse):
    reference: Optional[str] = None
    full_name: str


class AMLBatchResponse(BaseModel):
    request_id: str
    list_version: Optional[str] = None
    total: int
    with_matches: int
    results: List[AMLBatchResult]
