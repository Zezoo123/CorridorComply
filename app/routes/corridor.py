"""
Corridor decisions: apply a corridor ruleset on top of screening (run here)
and KYC results (supplied) to get approve / review / reject with reasons.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..config import DEFAULT_TENANT
from ..core.logger import log_audit_event
from ..corridor.engine import decide, registry
from ..corridor.schema import FIELDS
from ..db.database import get_session
from ..models.corridor import DecisionRequest, DecisionResponse, DispositionIn
from ..services import records
from ..services.aml_service import AMLService

logger = logging.getLogger(__name__)
router = APIRouter()


def _tenant(request: Request) -> str:
    return getattr(request.state, "tenant", None) or DEFAULT_TENANT


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:8]}"


@router.get("/corridors")
async def list_corridors():
    """Corridor rulesets loaded from the rules directory, with their review status."""
    reg = registry()
    return {
        "corridors": [{"id": r.id, "title": r.title, "version": r.version, "status": r.status,
                       "reviewed_by": r.reviewed_by, "rules": len(r.rules),
                       "sending": r.sending.country, "receiving": r.receiving.country} for r in reg.list()],
        "errors": reg.errors,
    }


@router.get("/corridors/fields")
async def rule_fields():
    """The fields a rule condition may reference, with their meaning."""
    return {"fields": FIELDS}


@router.get("/corridors/{corridor_id}")
async def get_corridor(corridor_id: str):
    try:
        return registry().get(corridor_id).model_dump()
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/decision", response_model=DecisionResponse)
async def make_decision(request: Request, payload: DecisionRequest, session: Session = Depends(get_session)):
    """
    Screen the customer, apply the corridor's rules, store the decision.

    The outcome is the most severe of all rules that fired; every reason is
    returned and stored so a reviewer sees the whole picture.
    """
    request_id = _rid(request)
    tenant = _tenant(request)
    try:
        ruleset = registry().get(payload.corridor)
    except KeyError as e:
        raise HTTPException(404, str(e))

    c = payload.customer
    screening = AMLService.screen_sync(
        c.full_name, dob=c.dob, nationality=c.nationality, entity_type=c.entity_type, request_id=request_id,
        threshold=ruleset.screening.threshold, use_variants=ruleset.screening.screen_name_variants,
        id_numbers=[c.document_number] if c.document_number else None,
    )
    customer = None
    if c.reference:
        customer = records.upsert_customer(session, tenant, c.reference, c.full_name, dob=c.dob,
                                           nationality=c.nationality, entity_type=c.entity_type, monitored=True)
    screening_row = records.save_screening(session, tenant, screening, request_id=request_id, channel="decision",
                                           full_name=c.full_name, dob=c.dob, nationality=c.nationality,
                                           entity_type=c.entity_type, customer=customer)

    customer_data = c.model_dump(exclude_none=True)
    beneficiary_data = payload.beneficiary.model_dump(exclude_none=True) if payload.beneficiary else None
    decision = decide(ruleset, customer_data, screening,
                      kyc=payload.kyc.model_dump(exclude_none=True) if payload.kyc else None,
                      beneficiary=beneficiary_data,
                      transfer=payload.transfer.model_dump(exclude_none=True) if payload.transfer else None)
    row = records.save_decision(session, tenant, decision, customer_data=customer_data, beneficiary_data=beneficiary_data,
                                screening=screening_row, customer=customer, request_id=request_id)

    log_audit_event(
        event_type="corridor_decision",
        data={"status": "success", "corridor": decision["corridor"], "ruleset_version": decision["ruleset_version"],
              "ruleset_status": decision["ruleset_status"], "outcome": decision["outcome"], "risk_score": decision["risk_score"],
              "rules_fired": [r["rule"] for r in decision["reasons"]], "decision_id": row.id, "screening_id": screening_row.id,
              "list_version": screening["list_version"]},
        request=request, request_payload=payload,
    )
    screening_public = {k: v for k, v in screening.items() if k not in ("risk_factors",)}
    screening_public["risk_level"] = getattr(screening["risk_level"], "value", str(screening["risk_level"]))
    return DecisionResponse(
        request_id=request_id, decision_id=row.id, screening=screening_public, screening_id=screening_row.id,
        list_version=screening["list_version"], **{k: v for k, v in decision.items() if k not in ("facts",)}, facts=decision["facts"],
    )


@router.get("/decisions")
async def list_decisions(request: Request, outcome: Optional[str] = Query(None, pattern="^(approve|review|reject)$"),
                         pending: Optional[bool] = Query(None, description="true: awaiting a reviewer; false: dispositioned"),
                         corridor: Optional[str] = None, limit: int = Query(100, ge=1, le=1000),
                         session: Session = Depends(get_session)):
    rows = records.decisions_for(session, _tenant(request), limit=limit, outcome=outcome, pending=pending, corridor=corridor)
    return {"decisions": [records.decision_to_dict(d) for d in rows], "count": len(rows)}


@router.post("/decisions/{decision_id}/disposition")
async def record_disposition(request: Request, decision_id: int, payload: DispositionIn, session: Session = Depends(get_session)):
    """The reviewer's call on a decision: approved, rejected or escalated, with a mandatory reason and name."""
    try:
        row = records.disposition(session, _tenant(request), decision_id, payload.outcome, payload.reason, payload.by)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if row is None:
        raise HTTPException(404, "Decision not found")
    log_audit_event("decision_disposition", {"status": "success", "decision_id": decision_id, "disposition": payload.outcome,
                                             "reason": payload.reason, "by": payload.by, "channel": "api"}, request=request)
    return records.decision_to_dict(row)


@router.get("/customers/{reference}/evidence")
async def customer_evidence(request: Request, reference: str, session: Session = Depends(get_session)):
    """Everything on file for one customer: profile, screenings, decisions with dispositions, alerts, list versions."""
    bundle = records.evidence_bundle(session, _tenant(request), reference)
    if bundle is None:
        raise HTTPException(404, "Customer not found")
    log_audit_event("evidence_exported", {"status": "success", "reference": reference}, request=request)
    return bundle


@router.get("/decisions/{decision_id}")
async def get_decision(request: Request, decision_id: int, session: Session = Depends(get_session)):
    from ..db.models import Decision
    tenant = records.get_or_create_tenant(session, _tenant(request))
    row = session.get(Decision, decision_id)
    if row is None or row.tenant_id != tenant.id:
        raise HTTPException(404, "Decision not found")
    return records.decision_to_dict(row)
