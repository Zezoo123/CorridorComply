from fastapi import APIRouter, HTTPException, status, Request
import base64
from io import BytesIO
from PIL import Image
import logging
import uuid
from datetime import datetime
from typing import Dict, Any
from starlette.datastructures import Headers

from app.core.logger import log_audit_event
from app.services.kyc_service import KYCService
from app.models.kyc import (
    KYCRequest,
    KYCResponse,
    KYCDocumentVerification,
    KYCMatchResult,
    KYCFaceMatch
)

router = APIRouter()
logger = logging.getLogger(__name__)

def decode_base64_image(image_data: str) -> Image.Image:
    """Decode base64 image data to PIL Image."""
    try:
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        
        # Decode base64
        image_bytes = base64.b64decode(image_data)
        return Image.open(BytesIO(image_bytes))
    except Exception as e:
        logger.error(f"Failed to decode image: {str(e)}")
        raise ValueError(f"Invalid image data: {str(e)}")

@router.post("/verify", response_model=KYCResponse)
async def verify_kyc(
    request: Request,
    payload: KYCRequest
):
    """
    Process KYC verification with document and selfie images.
    
    Returns verification results including risk score and level.
    """
    request_id = request.headers.get('X-Request-ID', f"req_{str(uuid.uuid4())[:8]}")
    logger.info(
        "Starting KYC verification",
        extra={
            'request_id': request_id,
            'document_type': payload.document_data.document_type,
            'issuing_country': payload.document_data.issuing_country,
            'nationality': payload.document_data.nationality,
            'first_name': payload.document_data.first_name,
            'last_name': payload.document_data.last_name
        }
    )
    
    try:
        # Process document image
        try:
            document_image = decode_base64_image(payload.document_image_base64)
            logger.info(
                f"Document image loaded: {document_image.size[0]}x{document_image.size[1]} {document_image.mode}",
                extra={'request_id': request_id}
            )
        except ValueError as e:
            error_msg = f"Invalid document image: {str(e)}"
            logger.error(error_msg, extra={'request_id': request_id})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid document image", "details": str(e)}
            )
        
        # Process selfie image
        try:
            selfie_image = decode_base64_image(payload.selfie_image_base64)
            logger.info(
                f"Selfie image loaded: {selfie_image.size[0]}x{selfie_image.size[1]} {selfie_image.mode}",
                extra={'request_id': request_id}
            )
        except ValueError as e:
            error_msg = f"Invalid selfie image: {str(e)}"
            logger.error(error_msg, extra={'request_id': request_id})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid selfie image", "details": str(e)}
            )
        
        # Call the KYC service
        kyc_result = await KYCService.process_kyc(
            request_id=request_id,
            full_name=f"{payload.document_data.first_name} {payload.document_data.last_name}",
            dob=payload.document_data.date_of_birth,
            nationality=payload.document_data.nationality,
            document_type=payload.document_data.document_type,
            document_number=payload.document_data.document_number,
            document_image=document_image,
            selfie_image=selfie_image,
            expiry_date=payload.document_data.expiry_date,
            issuing_country=payload.document_data.issuing_country
        )
        
        # Create the response with the correct field names matching KYCResponse model
        response = KYCResponse(
            request_id=request_id,
            status="completed",
            risk_score=kyc_result.get("risk_score", 0),
            risk_level=kyc_result.get("risk_level", "low"),
            verification_result=kyc_result.get("verification_result", {}),
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Log successful verification
        logger.info(
            "KYC verification completed",
            extra={
                'request_id': request_id,
                'risk_score': response.risk_score,
                'risk_level': response.risk_level,
                'document_verified': response.verification_result.get('document_verified', False) if response.verification_result else False,
                'face_match': response.verification_result.get('face_match', False) if response.verification_result else False
            }
        )
        
        # Create request with X-Request-ID header for audit logging
        headers = dict(request.headers)
        headers['X-Request-ID'] = request_id
        request_with_id = Request(scope=request.scope, receive=request.receive)
        request_with_id._headers = Headers(headers)
        
        # Create audit log
        log_audit_event(
            event_type="kyc_verification",
            data={
                "status": "success",
                "risk_score": response.risk_score,
                "risk_level": response.risk_level,
                "verification_result": response.verification_result,
                "document_type": payload.document_data.document_type,
                "issuing_country": payload.document_data.issuing_country,
                "nationality": payload.document_data.nationality,
                "document_verified": response.verification_result.get('document_verified', False) if response.verification_result else False,
                "face_match": response.verification_result.get('face_match', False) if response.verification_result else False,
                "metadata": getattr(payload, 'metadata', {})
            },
            request=request_with_id
        )
        
        # Return the response object which will be converted to JSON by FastAPI
        return response

    except HTTPException:
        # Re-raise HTTP exceptions as they're already properly formatted
        raise
        
    except Exception as e:
        error_msg = f"KYC verification failed: {str(e)}"
        logger.error(
            error_msg,
            extra={
                'request_id': request_id,
                'error': str(e),
                'document_type': getattr(payload.document_data, 'document_type', None) if hasattr(payload, 'document_data') else None
            },
            exc_info=True
        )
        
        # Create request with X-Request-ID header for audit logging
        headers = dict(request.headers)
        headers['X-Request-ID'] = request_id
        request_with_id = Request(scope=request.scope, receive=request.receive)
        request_with_id._headers = Headers(headers)
        
        # Create error audit log
        log_audit_event(
            event_type="kyc_verification",
            data={
                "status": "error",
                "error": str(e),
                "document_type": getattr(payload.document_data, 'document_type', None) if hasattr(payload, 'document_data') else None,
                "metadata": getattr(payload, 'metadata', {})
            },
            request=request_with_id
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "KYC verification failed",
                "request_id": request_id,
                "details": str(e)
            }
        )