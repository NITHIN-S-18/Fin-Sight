"""add authenticated goal monthly savings plan

Revision ID: 016_goal_monthly_plan
Revises: 015_add_financial_goal_name
"""

from alembic import op
import sqlalchemy as sa

revision = "016_goal_monthly_plan"
down_revision = "015_add_financial_goal_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("financial_goals", sa.Column("planned_monthly_contribution", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("financial_goals", "planned_monthly_contribution")
