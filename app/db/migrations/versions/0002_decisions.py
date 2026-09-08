"""Corridor decisions

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), index=True),
        sa.Column("screening_id", sa.Integer, sa.ForeignKey("screenings.id")),
        sa.Column("request_id", sa.String(64), index=True),
        sa.Column("corridor", sa.String(5), nullable=False, index=True),
        sa.Column("ruleset_version", sa.String(20), nullable=False),
        sa.Column("ruleset_status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("outcome", sa.String(10), nullable=False, index=True),
        sa.Column("risk_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reasons", sa.JSON, nullable=False),
        sa.Column("actions", sa.JSON, nullable=False),
        sa.Column("facts", sa.JSON, nullable=False),
        sa.Column("customer_data", sa.JSON, nullable=False),
        sa.Column("beneficiary_data", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_decisions_tenant_created", "decisions", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("decisions")
