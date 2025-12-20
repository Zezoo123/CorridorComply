import uuid
from fastapi import APIRouter, Request, status, HTTPException
from starlette.datastructures import Headers
import logging
from datetime import datetime
from ..models.aml import AMLScreenRequest, AMLScreenResponse, MatchResult
from ..services.aml_service import AMLService
from ..core.logger import log_audit_event

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/screen", response_model=AMLScreenResponse)
async def screen_aml(
    request: Request,
    payload: AMLScreenRequest
):
    """
    Screen an individual against AML/CFT databases.
    
    This endpoint checks if the provided individual matches any entries in
    sanctions lists, PEP databases, or other watchlists.
    """
    request_id = request.headers.get('X-Request-ID', f"req_{str(uuid.uuid4())[:8]}")
    
    try:
        # Log the start of AML screening
        logger.info(
            "Starting AML screening",
            extra={
                "request_id": request_id,
                "full_name": payload.full_name,
                "nationality": payload.nationality,
                "dob": payload.dob
            }
        )
        
        # Perform the AML screening (note: await is required for async functions)
        result = await AMLService.screen(
            request_id=request_id,
            full_name=payload.full_name,
            dob=payload.dob,
            nationality=payload.nationality
        )
        
        # Create the response
        response = AMLScreenResponse(**result)
        
        # Log successful screening
        logger.info(
            "AML screening completed successfully",
            extra={
                "request_id": request_id,
                "sanctions_match": response.sanctions_match,
                "pep_match": response.pep_match,
                "risk_score": response.risk_score,
                "risk_level": response.risk_level.value
            }
        )
        
        # Create a new request with the X-Request-ID header set
        headers = dict(request.headers)
        headers['X-Request-ID'] = request_id
        request_with_id = Request(scope=request.scope, receive=request.receive)
        request_with_id._headers = Headers(headers)
        
        # Log audit event
        log_audit_event(
            event_type="aml_screening",
            data={
                "status": "success",
                "full_name": payload.full_name,
                "nationality": payload.nationality,
                "sanctions_match": response.sanctions_match,
                "pep_match": response.pep_match,
                "risk_score": response.risk_score,
                "risk_level": response.risk_level.value,
                "match_count": len(response.matches),
                "details": response.details
            },
            request=request_with_id,
            request_payload=payload
        )
        
        return response
        
    except Exception as e:
        # Log the error
        logger.error(
            f"AML screening failed: {str(e)}",
            extra={
                "request_id": request_id,
                "error": str(e),
                "full_name": payload.full_name,
                "nationality": payload.nationality,
                "dob": payload.dob
            },
            exc_info=True
        )
        
        # Create a new request with the X-Request-ID header set
        headers = dict(request.headers)
        headers['X-Request-ID'] = request_id
        request_with_id = Request(scope=request.scope, receive=request.receive)
        request_with_id._headers = Headers(headers)
        
        # Log audit event for failure
        log_audit_event(
            event_type="aml_screening",
            data={
                "status": "error",
                "error": str(e),
                "full_name": payload.full_name,
                "nationality": payload.nationality
            },
            request=request_with_id,
            request_payload=payload
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "AML screening failed",
                "request_id": request_id,
                "details": str(e)
            }
        )