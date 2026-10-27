"""add auth session version

Revision ID: 010_add_auth_session_version
Revises: 009_add_auth_display_name
"""

from alembic import op
import sqlalchemy as sa


revision = "010_add_auth_session_version"
down_revision = "009_add_auth_display_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_users",
        sa.Column("session_version", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("auth_users", "session_version")
