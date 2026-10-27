"""create financial goals

Revision ID: 014_create_financial_goals
Revises: 013_trial_intelligence
"""

from alembic import op
import sqlalchemy as sa


revision = "014_create_financial_goals"
down_revision = "013_trial_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_goals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("goal_amount", sa.Float(), nullable=False),
        sa.Column("timeframe_months", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("evaluation", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_goals_user_id", "financial_goals", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_financial_goals_user_id", table_name="financial_goals")
    op.drop_table("financial_goals")
