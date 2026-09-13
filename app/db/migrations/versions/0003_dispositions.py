"""Reviewer dispositions on decisions

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("decisions") as b:
        b.add_column(sa.Column("disposition", sa.String(12), nullable=True))
        b.add_column(sa.Column("disposition_reason", sa.Text, nullable=True))
        b.add_column(sa.Column("disposition_by", sa.String(200), nullable=True))
        b.add_column(sa.Column("disposition_at", sa.DateTime, nullable=True))
    op.create_index("ix_decisions_disposition", "decisions", ["disposition"])


def downgrade() -> None:
    op.drop_index("ix_decisions_disposition", table_name="decisions")
    with op.batch_alter_table("decisions") as b:
        for c in ("disposition_at", "disposition_by", "disposition_reason", "disposition"):
            b.drop_column(c)
