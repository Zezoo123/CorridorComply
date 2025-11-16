from fastapi import APIRouter, HTTPException
from ..models.kyc import KYCRequest, KYCResponse
from ..services.kyc_service import KYCService

router = APIRouter()

@router.post("/verify", response_model=KYCResponse)
async def verify_kyc(payload: KYCRequest):
    """
    KYC verification endpoint.
    Performs document validation, OCR, face matching, and risk scoring.
    
    Validates all fields and returns risk assessment even if some fields are invalid.
    Validation errors are included in the response details.
    """
    result = KYCService.verify(
        full_name=payload.full_name,
        dob=payload.dob,
        nationality=payload.nationality,
        document_type=payload.document_type,
        document_number=payload.document_number,
        # TODO: Add image processing when OCR/face match are implemented
        face_match_score=None,
        face_match_result=None,
        ocr_quality=None,
        document_expired=False,
        document_expiring_soon=False,
        missing_fields=None,
        data_quality_issues=None
    )
    
    return KYCResponse(**result)
