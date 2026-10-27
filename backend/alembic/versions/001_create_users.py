"""create users

Revision ID: 001_create_users
Revises: 
Create Date: 2026-08-19 09:05:31.907000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_create_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("persona", sa.String(length=150), nullable=False),
        sa.Column("age_group", sa.String(length=50), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("income_type", sa.String(length=100), nullable=True),
        sa.Column("monthly_financial_capacity", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_users_user_id"),
    )


def downgrade() -> None:
    op.drop_table("users")
