"""Reviewer dispositions on screening hits

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("screenings") as b:
        b.add_column(sa.Column("disposition", sa.String(12), nullable=True))
        b.add_column(sa.Column("disposition_reason", sa.Text, nullable=True))
        b.add_column(sa.Column("disposition_by", sa.String(200), nullable=True))
        b.add_column(sa.Column("disposition_at", sa.DateTime, nullable=True))
    op.create_index("ix_screenings_disposition", "screenings", ["disposition"])


def downgrade() -> None:
    op.drop_index("ix_screenings_disposition", table_name="screenings")
    with op.batch_alter_table("screenings") as b:
        for c in ("disposition_at", "disposition_by", "disposition_reason", "disposition"):
            b.drop_column(c)
