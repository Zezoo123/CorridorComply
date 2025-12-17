"""
Combined risk assessment endpoint
"""
import uuid
from fastapi import APIRouter, Request, HTTPException, status
from typing import Dict, Any, Optional
import logging
from starlette.datastructures import Headers

from ..models.risk import CombinedRiskRequest, CombinedRiskResponse, RiskLevel
from ..services.aml_service import AMLService
from ..services.kyc_service import KYCService
from ..core.logger import log_audit_event

router = APIRouter()
logger = logging.getLogger(__name__)

# No need to instantiate services with only static/class methods

@router.post("/combined", response_model=CombinedRiskResponse)
async def get_combined_risk(
    request: Request,
    payload: CombinedRiskRequest
):
    """
    Calculate combined risk score from both AML and KYC checks.
    
    You can provide:
    - Raw data (aml_data and/or kyc_data) - will compute risk scores
    - Pre-calculated risk scores (aml_risk and/or kyc_risk) - will use directly
    - Mix of both
    
    The combined risk score weights AML at 60% and KYC at 40% when both are provided.
    """
    # Get or generate request ID
    request_id = request.headers.get('X-Request-ID', f"req_{str(uuid.uuid4())[:8]}")
    
    try:
        # Log the start of combined risk assessment
        logger.info(
            "Starting combined risk assessment",
            extra={
                "request_id": request_id,
                "aml_full_name": payload.aml_data.full_name,
                "aml_nationality": payload.aml_data.nationality,
                "kyc_document_type": payload.kyc_data.document_data.document_type,
                "kyc_nationality": payload.kyc_data.document_data.nationality
            }
        )
        
        # Initialize variables
        risk_factors = []
        details = []
        
        # Process AML data using the same AMLService.screen() as the AML route
        logger.info(
            "Processing AML screening for combined risk assessment",
            extra={
                "request_id": request_id,
                "full_name": payload.aml_data.full_name,
                "nationality": payload.aml_data.nationality,
                "dob": payload.aml_data.dob
            }
        )
        aml_result = await AMLService.screen(
            request_id=request_id,
            full_name=payload.aml_data.full_name,
            dob=payload.aml_data.dob,
            nationality=payload.aml_data.nationality
        )
        
        if not isinstance(aml_result, dict):
            raise ValueError("Unexpected response format from AML service")
        
        # Extract AML risk data
        aml_risk_score = aml_result.get("risk_score", 0)
        aml_risk_level = aml_result.get("risk_level", "low")
        aml_risk_factors = aml_result.get("risk_factors", [])
        
        risk_factors.extend(aml_risk_factors)
        details.append(f"AML screening completed with risk score: {aml_risk_score}")
        aml_risk_data = {
            "risk_score": aml_risk_score,
            "risk_level": aml_risk_level,
            "risk_factors": aml_risk_factors
        }
        
        logger.info(
            "AML screening completed for combined risk assessment",
            extra={
                "request_id": request_id,
                "aml_risk_score": aml_risk_score,
                "aml_risk_level": aml_risk_level,
                "sanctions_match": aml_result.get("sanctions_match", False),
                "pep_match": aml_result.get("pep_match", False)
            }
        )
        
        # Process KYC data using the same KYCService.process_kyc() as the KYC route
        logger.info(
            "Processing KYC verification for combined risk assessment",
            extra={
                "request_id": request_id,
                "document_type": payload.kyc_data.document_data.document_type,
                "nationality": payload.kyc_data.document_data.nationality,
                "issuing_country": payload.kyc_data.document_data.issuing_country
            }
        )
        # Convert base64 images to PIL Images
        from PIL import Image, UnidentifiedImageError
        import base64
        from io import BytesIO
        
        try:
            # Decode and verify document image
            try:
                document_image = Image.open(BytesIO(base64.b64decode(payload.kyc_data.document_image_base64)))
                selfie_image = Image.open(BytesIO(base64.b64decode(payload.kyc_data.selfie_image_base64)))
            except (base64.binascii.Error, UnidentifiedImageError) as e:
                raise ValueError(f"Invalid image data: {str(e)}")
            
            # Use the same KYCService.process_kyc() as the KYC route
            kyc_result = await KYCService.process_kyc(
                request_id=request_id,
                full_name=f"{payload.kyc_data.document_data.first_name} {payload.kyc_data.document_data.last_name}",
                dob=payload.kyc_data.document_data.date_of_birth,
                nationality=payload.kyc_data.document_data.nationality,
                document_type=payload.kyc_data.document_data.document_type,
                document_number=payload.kyc_data.document_data.document_number,
                document_image=document_image,
                selfie_image=selfie_image
            )
            
            if not isinstance(kyc_result, dict):
                raise ValueError("Unexpected response format from KYC service")
                
            # Extract KYC risk data
            kyc_risk_score = kyc_result.get("risk_score", 0)
            kyc_risk_level = kyc_result.get("risk_level", "low")
            kyc_risk_factors = kyc_result.get("risk_factors", [])
            
            risk_factors.extend(kyc_risk_factors)
            details.append(f"KYC verification completed with status: {kyc_result.get('status')}")
            kyc_risk_data = {
                "risk_score": kyc_risk_score,
                "risk_level": kyc_risk_level,
                "risk_factors": kyc_risk_factors
            }
            
            logger.info(
                "KYC verification completed for combined risk assessment",
                extra={
                    "request_id": request_id,
                    "kyc_risk_score": kyc_risk_score,
                    "kyc_risk_level": kyc_risk_level,
                    "document_verified": kyc_result.get("verification_result", {}).get("document_verified", False),
                    "face_match": kyc_result.get("verification_result", {}).get("face_match", False)
                }
            )
                
        except Exception as e:
            error_msg = f"Error processing KYC data: {str(e)}"
            logger.error(error_msg, extra={"request_id": request_id}, exc_info=True)
            raise ValueError(error_msg) from e
        
        # Calculate combined risk score (weighted average: 60% AML, 40% KYC)
        aml_score = float(aml_risk_data.get("risk_score", 0))
        kyc_score = float(kyc_risk_data.get("risk_score", 0))
        combined_score = (aml_score * 0.6) + (kyc_score * 0.4)
        combined_score = round(combined_score, 2)  # Round to 2 decimal places
        
        # Determine risk level
        if combined_score >= 70:
            risk_level = RiskLevel.HIGH
        elif combined_score >= 30:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        # Create response
        response = CombinedRiskResponse(
            request_id=request_id,
            combined_risk_score=combined_score,
            combined_risk_level=risk_level,
            risk_factors=risk_factors,
            aml_risk_score=aml_result.get("risk_score") if isinstance(aml_result, dict) else None,
            aml_risk_level=RiskLevel(aml_result["risk_level"]) if (isinstance(aml_result, dict) and "risk_level" in aml_result) else None,
            kyc_risk_score=kyc_result.get("risk_score") if isinstance(kyc_result, dict) else None,
            kyc_risk_level=RiskLevel(kyc_result["risk_level"]) if (isinstance(kyc_result, dict) and "risk_level" in kyc_result) else None,
            details=details,
            aml_details=aml_result,
            kyc_details=kyc_result
        )
        
        # Log successful completion
        logger.info(
            "Combined risk assessment completed",
            extra={
                "request_id": request_id,
                "combined_risk_score": response.combined_risk_score,
                "combined_risk_level": response.combined_risk_level.value,
                "risk_factors_count": len(risk_factors)
            }
        )
        
        # Create request with X-Request-ID header for audit logging
        headers = dict(request.headers)
        headers['X-Request-ID'] = request_id
        request_with_id = Request(scope=request.scope, receive=request.receive)
        request_with_id._headers = Headers(headers)
        
        # Log audit event
        audit_data = {
            "status": "success",
            "combined_risk_score": response.combined_risk_score,
            "combined_risk_level": response.combined_risk_level.value,
            "aml_risk_score": response.aml_risk_score,
            "aml_risk_level": response.aml_risk_level.value if response.aml_risk_level else None,
            "kyc_risk_score": response.kyc_risk_score,
            "kyc_risk_level": response.kyc_risk_level.value if response.kyc_risk_level else None,
            "risk_factors_count": len(risk_factors),
            "aml_sanctions_match": aml_result.get("sanctions_match", False),
            "aml_pep_match": aml_result.get("pep_match", False),
            "kyc_document_verified": kyc_result.get("verification_result", {}).get("document_verified", False),
            "kyc_face_match": kyc_result.get("verification_result", {}).get("face_match", False)
        }
        
        log_audit_event(
            event_type="combined_risk_assessment",
            data=audit_data,
            request=request_with_id
        )
        
        return response
        
    except Exception as e:
        # Log the error
        logger.error(
            "Combined risk assessment failed",
            extra={
                "request_id": request_id,
                "error": str(e),
                "has_aml_data": payload.aml_data is not None,
                "has_kyc_data": payload.kyc_data is not None
            },
            exc_info=True
        )
        
        # Create request with X-Request-ID header for audit logging
        headers = dict(request.headers)
        headers['X-Request-ID'] = request_id
        request_with_id = Request(scope=request.scope, receive=request.receive)
        request_with_id._headers = Headers(headers)
        
        # Log audit event for failure
        log_audit_event(
            event_type="combined_risk_assessment",
            data={
                "status": "error",
                "error": str(e),
                "has_aml_data": payload.aml_data is not None,
                "has_kyc_data": payload.kyc_data is not None
            },
            request=request_with_id
        )
        
        # Re-raise the exception with proper error handling
        if isinstance(e, HTTPException):
            raise e
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Combined risk assessment failed",
                "request_id": request_id,
                "details": str(e)
            }
        )

