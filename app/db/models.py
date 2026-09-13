"""
Persistent records: who was screened, against which list version, what was
found, and what changed since. Every business row carries a tenant.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.utcnow()


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    api_keys: Mapped[List["ApiKey"]] = relationship(back_populates="tenant")


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(12), default="")
    label: Mapped[str] = mapped_column(String(200), default="")
    sandbox: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="api_keys")


class ListVersion(Base):
    """One combined sanctions file, identified by content checksum."""
    __tablename__ = "list_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(200), index=True)         # file name @ mtime
    checksum: Mapped[str] = mapped_column(String(64), unique=True)
    file_name: Mapped[str] = mapped_column(String(200))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    sources: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # {"OFAC": 18508, ...}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Customer(Base):
    """A party a tenant keeps on file for ongoing monitoring."""
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("tenant_id", "reference", name="uq_customer_ref"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    reference: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(500))
    dob: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(10), default="person")
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    screenings: Mapped[List["Screening"]] = relationship(back_populates="customer")


class Screening(Base):
    """One screening result: the evidence record."""
    __tablename__ = "screenings"
    __table_args__ = (Index("ix_screenings_tenant_created", "tenant_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    list_version_id: Mapped[int] = mapped_column(ForeignKey("list_versions.id"), index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), default="api")   # api | batch | web_upload | rescreen
    full_name: Mapped[str] = mapped_column(String(500))
    dob: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(10), default="person")
    sanctions_match: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(10), default="low")
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    matches: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    customer: Mapped[Optional[Customer]] = relationship(back_populates="screenings")
    list_version: Mapped[ListVersion] = relationship()

    def match_keys(self) -> set:
        return {f"{m.get('source')}:{m.get('dataid')}" for m in (self.matches or [])}


class Decision(Base):
    """A corridor decision: the ruleset applied, the outcome and every reason that fired."""
    __tablename__ = "decisions"
    __table_args__ = (Index("ix_decisions_tenant_created", "tenant_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    screening_id: Mapped[Optional[int]] = mapped_column(ForeignKey("screenings.id"), nullable=True)
    beneficiary_screening_id: Mapped[Optional[int]] = mapped_column(ForeignKey("screenings.id"), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    corridor: Mapped[str] = mapped_column(String(5), index=True)
    ruleset_version: Mapped[str] = mapped_column(String(20))
    ruleset_status: Mapped[str] = mapped_column(String(10), default="draft")
    outcome: Mapped[str] = mapped_column(String(10), index=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    reasons: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    actions: Mapped[List[str]] = mapped_column(JSON, default=list)
    facts: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    customer_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    beneficiary_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    # Reviewer disposition (the trail an inspector reads)
    disposition: Mapped[Optional[str]] = mapped_column(String(12), nullable=True, index=True)  # approved | rejected | escalated
    disposition_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    disposition_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    disposition_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    screening: Mapped[Optional[Screening]] = relationship(foreign_keys=[screening_id])
    beneficiary_screening: Mapped[Optional[Screening]] = relationship(foreign_keys=[beneficiary_screening_id])


class Alert(Base):
    """Raised when a monitored customer's screening result changes between list versions."""
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"))
    previous_screening_id: Mapped[Optional[int]] = mapped_column(ForeignKey("screenings.id"), nullable=True)
    list_version_id: Mapped[int] = mapped_column(ForeignKey("list_versions.id"))
    kind: Mapped[str] = mapped_column(String(20))   # new_hit | new_match | hit_cleared
    summary: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open | acknowledged
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    customer: Mapped[Customer] = relationship()
    screening: Mapped[Screening] = relationship(foreign_keys=[screening_id])
