import uuid
from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.orm import Session
import logging
from ..models.aml import (
    AMLScreenRequest, AMLScreenResponse, AMLBatchRequest, AMLBatchResponse, AMLBatchResult,
)
from ..services.aml_service import AMLService
from ..core.logger import log_audit_event
from ..db.database import get_session
from ..services import records

logger = logging.getLogger(__name__)

router = APIRouter()


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:8]}"


@router.post("/screen", response_model=AMLScreenResponse)
async def screen_aml(request: Request, payload: AMLScreenRequest, session: Session = Depends(get_session)):
    """
    Screen a person, company or vessel against the combined sanctions lists
    (UN, OFAC, UK, EU). Names and listed aliases are both searched; DOB and
    nationality, when supplied, are compared with the list entry.
    """
    request_id = _request_id(request)
    try:
        result = AMLService.screen_sync(
            payload.full_name, dob=payload.dob, nationality=payload.nationality, entity_type=payload.entity_type,
            request_id=request_id, id_numbers=payload.id_numbers,
        )
        row = records.save_screening(session, getattr(request.state, "tenant", "dev"), result, request_id=request_id,
                                     channel="api", full_name=payload.full_name, dob=payload.dob,
                                     nationality=payload.nationality, entity_type=payload.entity_type)
        result["screening_id"] = row.id
        response = AMLScreenResponse(**result)

        logger.info(
            "AML screening completed",
            extra={
                "request_id": request_id,
                "sanctions_match": response.sanctions_match,
                "risk_score": response.risk_score,
                "risk_level": response.risk_level.value,
                "match_count": len(response.matches),
            },
        )
        log_audit_event(
            event_type="aml_screening",
            data={
                "status": "success",
                "full_name": payload.full_name,
                "nationality": payload.nationality,
                "entity_type": payload.entity_type,
                "sanctions_match": response.sanctions_match,
                "pep_match": response.pep_match,
                "risk_score": response.risk_score,
                "risk_level": response.risk_level.value,
                "match_count": len(response.matches),
                "list_version": response.list_version,
                "details": response.details,
            },
            request=request,
            request_payload=payload,
        )
        return response

    except Exception as e:
        logger.error(f"AML screening failed: {str(e)}", extra={"request_id": request_id}, exc_info=True)
        log_audit_event(
            event_type="aml_screening",
            data={"status": "error", "error": str(e), "full_name": payload.full_name, "nationality": payload.nationality},
            request=request,
            request_payload=payload,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "AML screening failed", "request_id": request_id, "details": str(e)},
        )


@router.post("/screen/batch", response_model=AMLBatchResponse)
async def screen_batch(request: Request, payload: AMLBatchRequest, session: Session = Depends(get_session)):
    """Screen up to 5,000 records in one call. Each result carries the caller's reference."""
    request_id = _request_id(request)
    results = []
    list_version = None
    for item in payload.items:
        r = AMLService.screen_sync(item.full_name, dob=item.dob, nationality=item.nationality,
                                   entity_type=item.entity_type, request_id=request_id, id_numbers=item.id_numbers)
        list_version = r["list_version"]
        row = records.save_screening(session, getattr(request.state, "tenant", "dev"), r, request_id=request_id,
                                     channel="batch", full_name=item.full_name, dob=item.dob,
                                     nationality=item.nationality, entity_type=item.entity_type)
        r["screening_id"] = row.id
        results.append(AMLBatchResult(reference=item.reference, full_name=item.full_name, **r))
    with_matches = sum(1 for r in results if r.sanctions_match)
    log_audit_event(
        event_type="aml_batch_screening",
        data={"status": "success", "total": len(results), "with_matches": with_matches, "list_version": list_version},
        request=request,
    )
    return AMLBatchResponse(request_id=request_id, list_version=list_version, total=len(results),
                            with_matches=with_matches, results=results)
