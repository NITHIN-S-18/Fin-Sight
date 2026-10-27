"""add auth display name

Revision ID: 009_add_auth_display_name
Revises: 008_cascade_account_owned_data
"""

from alembic import op
import sqlalchemy as sa


revision = "009_add_auth_display_name"
down_revision = "008_cascade_account_owned_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_users", sa.Column("display_name", sa.String(length=150), nullable=True))


def downgrade() -> None:
    op.drop_column("auth_users", "display_name")
