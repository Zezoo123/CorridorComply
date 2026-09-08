"""Initial schema: tenants, api keys, list versions, customers, screenings, alerts

Revision ID: 0001
Revises:
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(200), nullable=False, server_default=""),
        sa.Column("webhook_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("prefix", sa.String(12), nullable=False, server_default=""),
        sa.Column("label", sa.String(200), nullable=False, server_default=""),
        sa.Column("sandbox", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("revoked_at", sa.DateTime),
    )
    op.create_table(
        "list_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("label", sa.String(200), nullable=False, index=True),
        sa.Column("checksum", sa.String(64), nullable=False, unique=True),
        sa.Column("file_name", sa.String(200), nullable=False),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sources", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("reference", sa.String(200), nullable=False),
        sa.Column("full_name", sa.String(500), nullable=False),
        sa.Column("dob", sa.String(10)),
        sa.Column("nationality", sa.String(100)),
        sa.Column("entity_type", sa.String(10), nullable=False, server_default="person"),
        sa.Column("monitored", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("tenant_id", "reference", name="uq_customer_ref"),
    )
    op.create_table(
        "screenings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), index=True),
        sa.Column("list_version_id", sa.Integer, sa.ForeignKey("list_versions.id"), nullable=False, index=True),
        sa.Column("request_id", sa.String(64), index=True),
        sa.Column("channel", sa.String(20), nullable=False, server_default="api"),
        sa.Column("full_name", sa.String(500), nullable=False),
        sa.Column("dob", sa.String(10)),
        sa.Column("nationality", sa.String(100)),
        sa.Column("entity_type", sa.String(10), nullable=False, server_default="person"),
        sa.Column("sanctions_match", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("risk_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("risk_level", sa.String(10), nullable=False, server_default="low"),
        sa.Column("match_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("matches", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_screenings_tenant_created", "screenings", ["tenant_id", "created_at"])
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("screening_id", sa.Integer, sa.ForeignKey("screenings.id"), nullable=False),
        sa.Column("previous_screening_id", sa.Integer, sa.ForeignKey("screenings.id")),
        sa.Column("list_version_id", sa.Integer, sa.ForeignKey("list_versions.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("summary", sa.Text, nullable=False, server_default=""),
        sa.Column("details", sa.JSON, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open", index=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("acknowledged_at", sa.DateTime),
        sa.Column("acknowledged_by", sa.String(200)),
        sa.Column("note", sa.Text),
    )


def downgrade() -> None:
    for t in ("alerts", "screenings", "customers", "list_versions", "api_keys", "tenants"):
        op.drop_table(t)
