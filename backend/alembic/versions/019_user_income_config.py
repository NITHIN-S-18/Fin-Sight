"""create user income config

Revision ID: 019_user_income_config
Revises: 018_add_auth_avatar_url
"""

from alembic import op
import sqlalchemy as sa


revision = "019_user_income_config"
down_revision = "018_add_auth_avatar_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_income_configurations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("income_mode", sa.String(length=20), nullable=False, server_default="auto"),
        sa.Column("manual_monthly_income", sa.Float(), nullable=True),
        sa.Column("expected_monthly_income", sa.Float(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_user_income_configurations_user_id"),
        "user_income_configurations",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_income_configurations_user_id"),
        table_name="user_income_configurations",
    )
    op.drop_table("user_income_configurations")
