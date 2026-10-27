"""create password reset otps

Revision ID: 021_create_password_reset_otps
Revises: 020_create_password_reset_tokens
"""

from alembic import op
import sqlalchemy as sa


revision = "021_create_password_reset_otps"
down_revision = "020_create_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_otps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("auth_user_id", sa.Integer(), nullable=False),
        sa.Column("otp_hash", sa.String(length=128), nullable=False),
        sa.Column("reset_token_hash", sa.String(length=128), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["auth_user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_password_reset_otps_auth_user_id"),
        "password_reset_otps",
        ["auth_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_password_reset_otps_reset_token_hash"),
        "password_reset_otps",
        ["reset_token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_password_reset_otps_expires_at"),
        "password_reset_otps",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_password_reset_otps_expires_at"),
        table_name="password_reset_otps",
    )
    op.drop_index(
        op.f("ix_password_reset_otps_reset_token_hash"),
        table_name="password_reset_otps",
    )
    op.drop_index(
        op.f("ix_password_reset_otps_auth_user_id"),
        table_name="password_reset_otps",
    )
    op.drop_table("password_reset_otps")
