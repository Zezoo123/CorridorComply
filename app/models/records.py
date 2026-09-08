from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .aml import EntityType


class CustomerIn(BaseModel):
    reference: str = Field(..., min_length=1, max_length=200, description="Your identifier for this customer")
    full_name: str = Field(..., min_length=2, max_length=500)
    dob: Optional[str] = Field(None, description="YYYY-MM-DD")
    nationality: Optional[str] = None
    entity_type: EntityType = "person"
    monitored: bool = Field(True, description="Re-screen automatically when lists change")


class CustomerBatchIn(BaseModel):
    customers: List[CustomerIn] = Field(..., min_length=1, max_length=5000)
    screen_now: bool = True


class AlertAck(BaseModel):
    by: Optional[str] = Field(None, max_length=200)
    note: Optional[str] = None


class TenantSettings(BaseModel):
    webhook_url: Optional[str] = Field(None, max_length=500, description="POST target for new alerts")
    name: Optional[str] = Field(None, max_length=200)
