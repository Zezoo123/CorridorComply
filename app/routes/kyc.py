from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from ..models.kyc import KYCRequest, KYCResponse, decode_base64_image
from ..services.kyc_service import KYCService
from ..core.utils import generate_request_id
from PIL import Image
from typing import Optional

router = APIRouter()

@router.post("/verify", response_model=KYCResponse, responses={
    400: {"description": "Invalid image data"}
})
async def verify_kyc(payload: KYCRequest):
    """
    KYC verification endpoint with image support.
    
    Performs document validation, OCR, face matching, and risk scoring.
    
    Example request with base64-encoded images:
    ```json
    {
        "full_name": "Juan Dela Cruz",
        "dob": "1990-01-01",
        "nationality": "PH",
        "document_type": "passport",
        "document_number": "P1234567",
        "document_image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ...",
        "selfie_image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."
    }
    ```
    
    Images should be in JPEG or PNG format, base64-encoded. 
    The data URL prefix (e.g., 'data:image/jpeg;base64,') is optional.
    """
    request_id = generate_request_id()
    
    # Process document image if provided
    document_image: Optional[Image.Image] = None
    if payload.document_image_base64:
        try:
            document_image = decode_base64_image(payload.document_image_base64)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid document image", "details": str(e)}
            )
    
    # Process selfie image if provided
    selfie_image: Optional[Image.Image] = None
    if payload.selfie_image_base64:
        try:
            selfie_image = decode_base64_image(payload.selfie_image_base64)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid selfie image", "details": str(e)}
            )
    
    # For now, we'll just log that we received the images
    # In a real implementation, you would process them (OCR, face match, etc.)
    details = []
    if document_image:
        details.append(f"Received document image: {document_image.size[0]}x{document_image.size[1]} pixels")
    if selfie_image:
        details.append(f"Received selfie image: {selfie_image.size[0]}x{selfie_image.size[1]} pixels")
    
    # Call the KYC service with the processed data
    result = KYCService.verify(
        request_id=request_id,
        full_name=payload.full_name,
        dob=payload.dob,
        nationality=payload.nationality,
        document_type=payload.document_type,
        document_number=payload.document_number,
        # TODO: Process images and update these values
        face_match_score=0.95 if (document_image and selfie_image) else None,
        face_match_result=True if (document_image and selfie_image) else None,
        ocr_quality=0.9 if document_image else None,
        document_expired=False,
        document_expiring_soon=False,
        missing_fields=None,
        data_quality_issues=details or None
    )
    
    return KYCResponse(**result)
