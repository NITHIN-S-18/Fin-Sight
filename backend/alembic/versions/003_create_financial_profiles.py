"""create financial_profiles

Revision ID: 003_create_financial_profiles
Revises: 002_create_transactions
Create Date: 2026-08-19 09:05:31.907000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_create_financial_profiles"
down_revision = "002_create_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("monthly_income", sa.Float(), nullable=True),
        sa.Column("financial_capacity", sa.Float(), nullable=True),
        sa.Column("monthly_commitments", sa.Float(), nullable=True),
        sa.Column("subscription_burden", sa.Float(), nullable=True),
        sa.Column("emi_burden", sa.Float(), nullable=True),
        sa.Column("bnpl_burden", sa.Float(), nullable=True),
        sa.Column("exposure_score", sa.Float(), nullable=True),
        sa.Column("health_score", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name="fk_financial_profiles_user_id_users"),
        sa.UniqueConstraint("user_id", name="uq_financial_profiles_user_id"),
    )


def downgrade() -> None:
    op.drop_table("financial_profiles")
