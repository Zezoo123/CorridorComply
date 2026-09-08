"""
Persistence for screenings, customers, list versions and alerts, plus the
re-screening job that turns a one-off check into ongoing monitoring.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Alert, ApiKey, Customer, Decision, ListVersion, Screening, Tenant
from .sanctions_loader import SanctionsLoader

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------- tenants
def get_or_create_tenant(session: Session, slug: str, name: str = "") -> Tenant:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        tenant = Tenant(slug=slug, name=name or slug)
        session.add(tenant)
        session.flush()
    return tenant


# ------------------------------------------------------------ list versions
def _file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_version_cache: Dict[str, int] = {}


def current_list_version(session: Session) -> ListVersion:
    """The ListVersion row for the list currently loaded, registering it on first sight."""
    label = SanctionsLoader.current_version()
    if label in _version_cache:
        lv = session.get(ListVersion, _version_cache[label])
        if lv is not None:
            return lv
    path = SanctionsLoader.current_path()
    checksum = _file_checksum(path) if path and path.exists() else hashlib.sha256(label.encode()).hexdigest()
    lv = session.scalar(select(ListVersion).where(ListVersion.checksum == checksum))
    if lv is None:
        df = SanctionsLoader.load()
        sources = df["source"].value_counts().to_dict() if "source" in df.columns else {}
        lv = ListVersion(label=label, checksum=checksum, file_name=path.name if path else label,
                         row_count=int(len(df)), sources={k: int(v) for k, v in sources.items()})
        session.add(lv)
        session.flush()
        logger.info(f"Registered list version {lv.id}: {label} ({lv.row_count} rows)")
    _version_cache[label] = lv.id
    return lv


# --------------------------------------------------------------- screenings
def save_screening(session: Session, tenant_slug: str, result: Dict[str, Any], *, request_id: Optional[str] = None,
                   channel: str = "api", full_name: str = "", dob: Optional[str] = None,
                   nationality: Optional[str] = None, entity_type: str = "person",
                   customer: Optional[Customer] = None) -> Screening:
    tenant = get_or_create_tenant(session, tenant_slug)
    lv = current_list_version(session)
    level = result["risk_level"]
    row = Screening(
        tenant_id=tenant.id, customer_id=customer.id if customer else None, list_version_id=lv.id,
        request_id=request_id, channel=channel, full_name=full_name, dob=dob or None,
        nationality=nationality or None, entity_type=entity_type,
        sanctions_match=bool(result["sanctions_match"]), risk_score=int(result["risk_score"]),
        risk_level=getattr(level, "value", str(level)), match_count=len(result["matches"]),
        matches=result["matches"],
    )
    session.add(row)
    session.flush()
    return row


def screenings_for(session: Session, tenant_slug: str, limit: int = 100) -> List[Screening]:
    tenant = get_or_create_tenant(session, tenant_slug)
    return list(session.scalars(
        select(Screening).where(Screening.tenant_id == tenant.id).order_by(Screening.id.desc()).limit(limit)))


# ---------------------------------------------------------------- customers
def upsert_customer(session: Session, tenant_slug: str, reference: str, full_name: str, *,
                    dob: Optional[str] = None, nationality: Optional[str] = None,
                    entity_type: str = "person", monitored: bool = True) -> Customer:
    tenant = get_or_create_tenant(session, tenant_slug)
    c = session.scalar(select(Customer).where(Customer.tenant_id == tenant.id, Customer.reference == reference))
    if c is None:
        c = Customer(tenant_id=tenant.id, reference=reference, full_name=full_name)
        session.add(c)
    c.full_name = full_name
    c.dob = dob or None
    c.nationality = nationality or None
    c.entity_type = entity_type
    c.monitored = monitored
    session.flush()
    return c


def customers_for(session: Session, tenant_slug: str, monitored_only: bool = False) -> List[Customer]:
    tenant = get_or_create_tenant(session, tenant_slug)
    q = select(Customer).where(Customer.tenant_id == tenant.id)
    if monitored_only:
        q = q.where(Customer.monitored.is_(True))
    return list(session.scalars(q.order_by(Customer.id)))


def latest_screening(session: Session, customer: Customer) -> Optional[Screening]:
    return session.scalar(select(Screening).where(Screening.customer_id == customer.id)
                          .order_by(Screening.id.desc()).limit(1))


# ------------------------------------------------------------- re-screening
def _diff_alert(previous: Optional[Screening], current: Screening) -> Optional[Dict[str, Any]]:
    """Decide whether the change between two screenings deserves an alert."""
    now_keys = current.match_keys()
    prev_keys = previous.match_keys() if previous else set()
    if current.sanctions_match and not (previous and previous.sanctions_match):
        names = sorted({m.get("sanctioned_name", "") for m in current.matches})[:5]
        return {"kind": "new_hit", "summary": f"New sanctions hit: {', '.join(names)}",
                "details": {"added": sorted(now_keys - prev_keys)}}
    added = now_keys - prev_keys
    if added:
        names = sorted({m.get("sanctioned_name", "") for m in current.matches
                        if f"{m.get('source')}:{m.get('dataid')}" in added})[:5]
        return {"kind": "new_match", "summary": f"New list entry matches this customer: {', '.join(names)}",
                "details": {"added": sorted(added)}}
    if previous and previous.sanctions_match and not current.sanctions_match:
        return {"kind": "hit_cleared", "summary": "Previous sanctions hit no longer matches the current list",
                "details": {"removed": sorted(prev_keys - now_keys)}}
    return None


def rescreen_tenant(session: Session, tenant_slug: str, *, only_if_new_version: bool = True) -> Dict[str, Any]:
    """Re-screen every monitored customer of a tenant against the current list.

    Returns a summary. Creates Alert rows for material changes and posts them
    to the tenant's webhook when one is configured.
    """
    from .aml_service import AMLService
    tenant = get_or_create_tenant(session, tenant_slug)
    lv = current_list_version(session)
    customers = customers_for(session, tenant_slug, monitored_only=True)
    summary = {"tenant": tenant_slug, "list_version": lv.label, "customers": len(customers),
               "rescreened": 0, "skipped": 0, "alerts": 0, "alert_ids": []}
    new_alerts: List[Alert] = []
    for c in customers:
        previous = latest_screening(session, c)
        if only_if_new_version and previous is not None and previous.list_version_id == lv.id:
            summary["skipped"] += 1
            continue
        result = AMLService.screen_sync(c.full_name, dob=c.dob, nationality=c.nationality,
                                        entity_type=c.entity_type, request_id=f"rescreen_{lv.id}")
        current = save_screening(session, tenant_slug, result, channel="rescreen", full_name=c.full_name,
                                 dob=c.dob, nationality=c.nationality, entity_type=c.entity_type, customer=c)
        summary["rescreened"] += 1
        change = _diff_alert(previous, current)
        if change:
            alert = Alert(tenant_id=tenant.id, customer_id=c.id, screening_id=current.id,
                          previous_screening_id=previous.id if previous else None, list_version_id=lv.id,
                          kind=change["kind"], summary=change["summary"], details=change["details"])
            session.add(alert)
            session.flush()
            new_alerts.append(alert)
            summary["alerts"] += 1
            summary["alert_ids"].append(alert.id)
    if new_alerts and tenant.webhook_url:
        _post_webhook(tenant, new_alerts, lv)
    return summary


def rescreen_all(session: Session) -> List[Dict[str, Any]]:
    return [rescreen_tenant(session, t.slug) for t in session.scalars(select(Tenant))]


def _post_webhook(tenant: Tenant, alerts: Iterable[Alert], lv: ListVersion) -> None:
    try:
        import requests
        payload = {"tenant": tenant.slug, "list_version": lv.label, "alerts": [alert_to_dict(a) for a in alerts]}
        r = requests.post(tenant.webhook_url, json=payload, timeout=5)
        logger.info(f"Webhook to {tenant.slug}: HTTP {r.status_code}")
    except Exception as e:  # never let a webhook failure break a re-screen
        logger.warning(f"Webhook to {tenant.slug} failed: {e}")


# ------------------------------------------------------------------- alerts
def alerts_for(session: Session, tenant_slug: str, status: Optional[str] = "open", limit: int = 200) -> List[Alert]:
    tenant = get_or_create_tenant(session, tenant_slug)
    q = select(Alert).where(Alert.tenant_id == tenant.id)
    if status:
        q = q.where(Alert.status == status)
    return list(session.scalars(q.order_by(Alert.id.desc()).limit(limit)))


def acknowledge_alert(session: Session, tenant_slug: str, alert_id: int, by: str = "", note: str = "") -> Optional[Alert]:
    tenant = get_or_create_tenant(session, tenant_slug)
    alert = session.get(Alert, alert_id)
    if alert is None or alert.tenant_id != tenant.id:
        return None
    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = by or None
    alert.note = note or None
    session.flush()
    return alert


def alert_to_dict(a: Alert) -> Dict[str, Any]:
    return {
        "id": a.id, "kind": a.kind, "status": a.status, "summary": a.summary, "details": a.details,
        "customer": {"id": a.customer.id, "reference": a.customer.reference, "full_name": a.customer.full_name,
                     "dob": a.customer.dob, "nationality": a.customer.nationality, "entity_type": a.customer.entity_type},
        "screening_id": a.screening_id, "previous_screening_id": a.previous_screening_id,
        "list_version_id": a.list_version_id, "created_at": a.created_at.isoformat(),
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "acknowledged_by": a.acknowledged_by, "note": a.note,
    }


def screening_to_dict(s: Screening) -> Dict[str, Any]:
    return {
        "id": s.id, "request_id": s.request_id, "channel": s.channel, "customer_id": s.customer_id,
        "full_name": s.full_name, "dob": s.dob, "nationality": s.nationality, "entity_type": s.entity_type,
        "sanctions_match": s.sanctions_match, "risk_score": s.risk_score, "risk_level": s.risk_level,
        "match_count": s.match_count, "matches": s.matches, "list_version": s.list_version.label,
        "created_at": s.created_at.isoformat(),
    }


def customer_to_dict(c: Customer, last: Optional[Screening] = None) -> Dict[str, Any]:
    d = {"id": c.id, "reference": c.reference, "full_name": c.full_name, "dob": c.dob, "nationality": c.nationality,
         "entity_type": c.entity_type, "monitored": c.monitored, "created_at": c.created_at.isoformat()}
    if last is not None:
        d["last_screening"] = {"id": last.id, "sanctions_match": last.sanctions_match, "risk_score": last.risk_score,
                               "risk_level": last.risk_level, "list_version": last.list_version.label,
                               "created_at": last.created_at.isoformat()}
    return d


# ---------------------------------------------------------------- decisions
def save_decision(session: Session, tenant_slug: str, decision: Dict[str, Any], *, customer_data: Dict[str, Any],
                  beneficiary_data: Optional[Dict[str, Any]] = None, screening: Optional[Screening] = None,
                  customer: Optional[Customer] = None, request_id: Optional[str] = None) -> Decision:
    tenant = get_or_create_tenant(session, tenant_slug)
    row = Decision(
        tenant_id=tenant.id, customer_id=customer.id if customer else None,
        screening_id=screening.id if screening else None, request_id=request_id,
        corridor=decision["corridor"], ruleset_version=decision["ruleset_version"],
        ruleset_status=decision["ruleset_status"], outcome=decision["outcome"],
        risk_score=int(decision["risk_score"]), reasons=decision["reasons"], actions=decision["actions"],
        facts=decision["facts"], customer_data=_strip_images(customer_data), beneficiary_data=beneficiary_data or {},
    )
    session.add(row)
    session.flush()
    return row


def _strip_images(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in (d or {}).items() if not str(k).endswith("_base64")}


def decisions_for(session: Session, tenant_slug: str, limit: int = 100, outcome: Optional[str] = None) -> List[Decision]:
    tenant = get_or_create_tenant(session, tenant_slug)
    q = select(Decision).where(Decision.tenant_id == tenant.id)
    if outcome:
        q = q.where(Decision.outcome == outcome)
    return list(session.scalars(q.order_by(Decision.id.desc()).limit(limit)))


def decision_to_dict(d: Decision) -> Dict[str, Any]:
    return {
        "id": d.id, "request_id": d.request_id, "corridor": d.corridor, "ruleset_version": d.ruleset_version,
        "ruleset_status": d.ruleset_status, "outcome": d.outcome, "risk_score": d.risk_score, "reasons": d.reasons,
        "actions": d.actions, "facts": d.facts, "customer": d.customer_data, "beneficiary": d.beneficiary_data,
        "screening_id": d.screening_id, "customer_id": d.customer_id,
        "list_version": d.screening.list_version.label if d.screening else None,
        "created_at": d.created_at.isoformat(),
    }
