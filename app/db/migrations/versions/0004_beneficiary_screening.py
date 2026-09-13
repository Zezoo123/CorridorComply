"""Beneficiary screening on decisions

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("decisions") as b:
        b.add_column(sa.Column("beneficiary_screening_id", sa.Integer, nullable=True))
        b.create_foreign_key("fk_decisions_beneficiary_screening", "screenings", ["beneficiary_screening_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("decisions") as b:
        b.drop_constraint("fk_decisions_beneficiary_screening", type_="foreignkey")
        b.drop_column("beneficiary_screening_id")
