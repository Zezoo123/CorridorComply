"""
Shared enumerations for the application models.
"""
from enum import Enum

class RiskLevel(str, Enum):
    """Risk level enumeration for all risk assessments"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class DocumentType(str, Enum):
    """Supported document types for KYC verification"""
    PASSPORT = "passport"
    NATIONAL_ID = "national_id"
    DRIVING_LICENSE = "driving_license"
    RESIDENCE_PERMIT = "residence_permit"

class VerificationStatus(str, Enum):
    """Status of a verification process"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
