"""
Corridor ruleset schema. A ruleset is a JSON file; this module is the contract
it must satisfy. The engine refuses to load a ruleset that fails validation.

Conditions are small and explicit on purpose so a compliance advisor can read a
rule and sign it. There is no embedded code.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Outcome = Literal["approve", "review", "reject"]
Severity = {"approve": 0, "review": 1, "reject": 2}

Operator = Literal["eq", "ne", "in", "not_in", "gte", "lte", "gt", "lt", "is_true", "is_false", "is_null", "not_null", "contains"]

# Fields a condition may reference. Documented so a reviewer knows the vocabulary.
FIELDS: Dict[str, str] = {
    "customer.entity_type": "person | entity | vessel",
    "customer.nationality": "ISO alpha-2",
    "customer.residence_country": "ISO alpha-2",
    "customer.document_type": "id type code, e.g. qatar_id, passport",
    "customer.age": "years, from dob",
    "customer.dob_present": "bool",
    "customer.id_valid": "bool: stated id number is well-formed",
    "customer.id_birth_year_matches": "bool|null: id-encoded birth year vs stated dob",
    "customer.id_nationality_matches": "bool|null: id-encoded nationality vs stated",
    "customer.missing_fields": "list of required fields not supplied",
    "customer.name_flags": "list: single_name, patronymic, compound_surname",
    "screening.match": "bool",
    "screening.match_count": "int",
    "screening.best_confidence": "high | medium | low | null",
    "screening.best_similarity": "0-100",
    "screening.best_dob_agreement": "exact | year | mismatch | unknown | null",
    "screening.best_country_match": "bool|null",
    "screening.best_match_type": "name | alias | null",
    "screening.best_source": "UN | OFAC | UK | EU",
    "screening.risk_score": "0-100",
    "kyc.document_verified": "bool|null",
    "kyc.face_match": "bool|null",
    "kyc.document_expired": "bool|null",
    "kyc.mrz_mismatches": "int|null",
    "kyc.liveness": "bool|null",
    "beneficiary.present": "bool",
    "beneficiary.id_valid": "bool|null",
    "beneficiary.country": "ISO alpha-2",
    "beneficiary.missing_fields": "list",
    "transfer.amount": "number in the corridor currency",
    "transfer.purpose": "string",
}


class Condition(BaseModel):
    field: str
    op: Operator = "eq"
    value: Any = None

    @field_validator("field")
    @classmethod
    def _known_field(cls, v: str) -> str:
        if v not in FIELDS:
            raise ValueError(f"unknown field '{v}'; allowed: {', '.join(sorted(FIELDS))}")
        return v


class When(BaseModel):
    all: List[Condition] = Field(default_factory=list)
    any: List[Condition] = Field(default_factory=list)

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.all and not self.any:
            raise ValueError("a rule needs at least one condition in 'all' or 'any'")
        return self


class Rule(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9_\-]+$")
    title: str
    when: When
    outcome: Outcome
    reason: str = Field(..., description="Shown to the reviewer and stored with the decision")
    risk_add: int = Field(0, ge=-100, le=100, description="Added to the risk score when the rule fires")
    actions: List[str] = Field(default_factory=list, description="e.g. escalate_mlro, request_source_of_funds, freeze_and_report")
    basis: Optional[str] = Field(None, description="Regulatory basis or source for the reviewer")


class DocumentSpec(BaseModel):
    type: str = Field(..., description="id type code, matches identifiers.check_id")
    label: str
    issuer: str = Field(..., description="ISO alpha-2 of the issuing country, or 'ANY'")
    customer_types: List[Literal["person", "entity"]] = Field(default_factory=lambda: ["person"])
    mrz: Optional[Literal["TD1", "TD3"]] = None
    required: bool = False
    notes: Optional[str] = None


class Side(BaseModel):
    country: str = Field(..., min_length=2, max_length=2)
    currency: Optional[str] = None
    regulators: List[str] = Field(default_factory=list)
    national_lists: List[str] = Field(default_factory=list, description="Lists that apply on this side beyond UN/OFAC/UK/EU")
    documents: List[DocumentSpec] = Field(default_factory=list)
    required_fields: Dict[str, List[str]] = Field(default_factory=dict, description="per customer type")
    notes: Optional[str] = None


class ScreeningPolicy(BaseModel):
    lists: List[str] = Field(default_factory=lambda: ["UN", "OFAC", "UK", "EU"])
    threshold: int = Field(85, ge=50, le=100)
    require_dob_for_single_names: bool = True
    screen_name_variants: bool = True
    high_risk_countries: List[str] = Field(default_factory=list, description="FATF call-for-action and the firm's own list")


class Reporting(BaseModel):
    fiu: Optional[str] = None
    portal: Optional[str] = None
    str_prefill_fields: List[str] = Field(default_factory=list)


class Ruleset(BaseModel):
    id: str = Field(..., pattern=r"^[A-Z]{2}-[A-Z]{2}$", description="SENDING-RECEIVING, e.g. QA-PH")
    version: str
    status: Literal["draft", "reviewed", "approved"] = "draft"
    reviewed_by: Optional[str] = None
    reviewed_on: Optional[str] = None
    title: str
    sending: Side
    receiving: Side
    screening: ScreeningPolicy = Field(default_factory=ScreeningPolicy)
    rules: List[Rule]
    reporting: Reporting = Field(default_factory=Reporting)
    sources: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _consistent(self):
        if self.id != f"{self.sending.country}-{self.receiving.country}":
            raise ValueError("ruleset id must be SENDING-RECEIVING country codes")
        ids = [r.id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule ids must be unique")
        if self.status != "draft" and not self.reviewed_by:
            raise ValueError("a reviewed or approved ruleset must name reviewed_by")
        return self
