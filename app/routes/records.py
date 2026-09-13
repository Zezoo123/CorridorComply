"""
Customers on file, ongoing monitoring, alerts and the screening history.
All routes are tenant-scoped through the API key.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..config import DEFAULT_TENANT
from ..core.logger import log_audit_event
from ..db.database import get_session
from ..models.records import AlertAck, CustomerBatchIn, CustomerIn, TenantSettings
from ..services import records
from ..services.aml_service import AMLService

logger = logging.getLogger(__name__)
router = APIRouter()


def _tenant(request: Request) -> str:
    return getattr(request.state, "tenant", None) or DEFAULT_TENANT


def _rid(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)


# ---------------------------------------------------------------- customers
@router.post("/customers", status_code=201)
async def upsert_customers(request: Request, payload: CustomerBatchIn, session: Session = Depends(get_session)):
    """Add or update customers (by your reference). Screens them immediately unless screen_now is false."""
    tenant = _tenant(request)
    out = []
    for c in payload.customers:
        cust = records.upsert_customer(session, tenant, c.reference, c.full_name, dob=c.dob, nationality=c.nationality,
                                       entity_type=c.entity_type, monitored=c.monitored)
        last = None
        if payload.screen_now:
            result = AMLService.screen_sync(c.full_name, dob=c.dob, nationality=c.nationality,
                                            entity_type=c.entity_type, request_id=_rid(request) or "")
            last = records.save_screening(session, tenant, result, request_id=_rid(request), channel="api",
                                          full_name=c.full_name, dob=c.dob, nationality=c.nationality,
                                          entity_type=c.entity_type, customer=cust)
        out.append(records.customer_to_dict(cust, last))
    log_audit_event("customers_upserted", {"status": "success", "count": len(out), "screened": payload.screen_now},
                    request=request)
    return {"customers": out, "count": len(out)}


@router.get("/customers")
async def list_customers(request: Request, monitored: Optional[bool] = None, session: Session = Depends(get_session)):
    tenant = _tenant(request)
    custs = records.customers_for(session, tenant, monitored_only=bool(monitored))
    return {"customers": [records.customer_to_dict(c, records.latest_screening(session, c)) for c in custs]}


@router.delete("/customers/{reference}")
async def stop_monitoring(request: Request, reference: str, session: Session = Depends(get_session)):
    """Stop monitoring a customer. The screening history is kept."""
    tenant = _tenant(request)
    for c in records.customers_for(session, tenant):
        if c.reference == reference:
            c.monitored = False
            session.flush()
            return {"reference": reference, "monitored": False}
    raise HTTPException(404, "Customer not found")


# --------------------------------------------------------------- monitoring
@router.post("/monitoring/rescreen")
async def rescreen(request: Request, force: bool = False, session: Session = Depends(get_session)):
    """Re-screen every monitored customer against the current list and raise alerts for changes.

    Skips customers already screened against the current list version unless force=true.
    """
    tenant = _tenant(request)
    summary = records.rescreen_tenant(session, tenant, only_if_new_version=not force)
    log_audit_event("monitoring_rescreen", {"status": "success", **{k: v for k, v in summary.items() if k != "alert_ids"}},
                    request=request)
    return summary


@router.get("/alerts")
async def list_alerts(request: Request, status: Optional[str] = Query("open", pattern="^(open|acknowledged|all)$"),
                      session: Session = Depends(get_session)):
    tenant = _tenant(request)
    alerts = records.alerts_for(session, tenant, status=None if status == "all" else status)
    return {"alerts": [records.alert_to_dict(a) for a in alerts], "count": len(alerts)}


@router.post("/alerts/{alert_id}/ack")
async def ack_alert(request: Request, alert_id: int, payload: AlertAck, session: Session = Depends(get_session)):
    tenant = _tenant(request)
    alert = records.acknowledge_alert(session, tenant, alert_id, by=payload.by or "", note=payload.note or "")
    if alert is None:
        raise HTTPException(404, "Alert not found")
    log_audit_event("alert_acknowledged", {"status": "success", "alert_id": alert_id, "by": payload.by, "note": payload.note},
                    request=request)
    return records.alert_to_dict(alert)


# --------------------------------------------------------------- screenings
@router.get("/screenings")
async def list_screenings(request: Request, limit: int = Query(100, ge=1, le=1000), session: Session = Depends(get_session)):
    """Screening history for this tenant, newest first."""
    tenant = _tenant(request)
    rows = records.screenings_for(session, tenant, limit=limit)
    return {"screenings": [records.screening_to_dict(s) for s in rows], "count": len(rows)}


@router.get("/screenings/{screening_id}")
async def get_screening(request: Request, screening_id: int, session: Session = Depends(get_session)):
    from ..db.models import Screening
    tenant = records.get_or_create_tenant(session, _tenant(request))
    row = session.get(Screening, screening_id)
    if row is None or row.tenant_id != tenant.id:
        raise HTTPException(404, "Screening not found")
    return records.screening_to_dict(row)


# ------------------------------------------------------------------- tenant
@router.get("/tenant")
async def tenant_settings(request: Request, session: Session = Depends(get_session)):
    t = records.get_or_create_tenant(session, _tenant(request))
    return {"slug": t.slug, "name": t.name, "webhook_url": t.webhook_url}


@router.put("/tenant")
async def update_tenant(request: Request, payload: TenantSettings, session: Session = Depends(get_session)):
    t = records.get_or_create_tenant(session, _tenant(request))
    if payload.webhook_url is not None:
        t.webhook_url = payload.webhook_url or None
    if payload.name is not None:
        t.name = payload.name
    session.flush()
    return {"slug": t.slug, "name": t.name, "webhook_url": t.webhook_url}


@router.get("/lists/current")
async def current_list(session: Session = Depends(get_session)):
    """Identity of the sanctions list currently loaded."""
    lv = records.current_list_version(session)
    return {"id": lv.id, "label": lv.label, "file_name": lv.file_name, "checksum": lv.checksum,
            "row_count": lv.row_count, "sources": lv.sources, "registered_at": lv.created_at.isoformat()}
