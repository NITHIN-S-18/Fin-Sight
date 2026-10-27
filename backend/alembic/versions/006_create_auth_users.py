"""create auth users

Revision ID: 006_create_auth_users
Revises: 005_expand_financial_profiles
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "006_create_auth_users"
down_revision = "005_expand_financial_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email", name="uq_auth_users_email"),
    )
    op.create_index(op.f("ix_auth_users_email"), "auth_users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_users_email"), table_name="auth_users")
    op.drop_table("auth_users")