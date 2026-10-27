"""add persistent financial goal name

Revision ID: 015_add_financial_goal_name
Revises: 014_create_financial_goals
"""

from alembic import op
import sqlalchemy as sa


revision = "015_add_financial_goal_name"
down_revision = "014_create_financial_goals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("financial_goals", sa.Column("goal_name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("financial_goals", "goal_name")
