from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .aml import EntityType


class CustomerIn(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=500)
    dob: Optional[str] = Field(None, description="YYYY-MM-DD")
    nationality: Optional[str] = Field(None, description="ISO alpha-2")
    residence_country: Optional[str] = None
    entity_type: EntityType = "person"
    document_type: Optional[str] = Field(None, description="qatar_id | passport | pk_cnic | in_aadhaar | bd_nid | ph_philsys | commercial_registration ...")
    document_number: Optional[str] = None
    document_expiry: Optional[str] = None
    place_of_birth: Optional[str] = None
    mobile: Optional[str] = None
    address_qatar: Optional[str] = None
    profession: Optional[str] = None
    employer_sponsor: Optional[str] = None
    pep: Optional[bool] = Field(None, description="Politically exposed person, self-declared or from a PEP source")
    is_resident: Optional[bool] = None
    first_transaction: Optional[bool] = None
    registered_address: Optional[str] = None
    ubo_names: Optional[List[str]] = None
    purpose: Optional[str] = None
    reference: Optional[str] = Field(None, description="Your customer id; when given the customer is put on file for monitoring")


class BeneficiaryIn(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=500)
    country: str = Field(..., min_length=2, max_length=2)
    relationship: Optional[str] = None
    payout_channel: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    dob: Optional[str] = None


class KycIn(BaseModel):
    """Results of a document/face check done elsewhere (or by /kyc/verify)."""
    document_verified: Optional[bool] = None
    face_match: Optional[bool] = None
    document_expired: Optional[bool] = None
    mrz_mismatches: Optional[int] = None
    liveness: Optional[bool] = None


class TransferIn(BaseModel):
    amount: Optional[float] = Field(None, description="In the sending currency")
    currency: Optional[str] = None
    receive_amount: Optional[float] = Field(None, description="In the receiving currency")
    receive_currency: Optional[str] = None
    purpose: Optional[str] = None
    purpose_category: Optional[str] = Field(None, description="family_support | charity | business | education | medical | savings | other")


class DecisionRequest(BaseModel):
    corridor: str = Field(..., pattern=r"^[A-Za-z]{2}-[A-Za-z]{2}$", json_schema_extra={"example": "QA-PH"})
    customer: CustomerIn
    beneficiary: Optional[BeneficiaryIn] = None
    kyc: Optional[KycIn] = None
    transfer: Optional[TransferIn] = None


class DecisionResponse(BaseModel):
    request_id: str
    decision_id: Optional[int] = None
    corridor: str
    ruleset_version: str
    ruleset_status: str
    outcome: str
    risk_score: int
    reasons: List[Dict[str, Any]]
    actions: List[str]
    screening: Dict[str, Any]
    screening_id: Optional[int] = None
    list_version: Optional[str] = None
    id_check: Optional[Dict[str, Any]] = None
    beneficiary_id_check: Optional[Dict[str, Any]] = None
    name_analysis: Optional[Dict[str, Any]] = None
    facts: Dict[str, Any]


class DispositionIn(BaseModel):
    outcome: str = Field(..., pattern=r"^(approved|rejected|escalated)$")
    reason: str = Field(..., min_length=3, max_length=4000, description="What an inspector will read")
    by: str = Field(..., min_length=2, max_length=200, description="Reviewer's name")
