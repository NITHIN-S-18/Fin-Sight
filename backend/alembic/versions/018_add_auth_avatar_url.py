"""add auth avatar url

Revision ID: 018_add_auth_avatar_url
Revises: 017_create_conversations
"""

from alembic import op
import sqlalchemy as sa


revision = "018_add_auth_avatar_url"
down_revision = "017_create_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_users", sa.Column("avatar_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("auth_users", "avatar_url")
