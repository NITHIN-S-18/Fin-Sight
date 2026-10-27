"""create detected recurring payments

Revision ID: 011_create_recurring_payments
Revises: 010_add_auth_session_version
"""

from alembic import op
import sqlalchemy as sa


revision = "011_create_recurring_payments"
down_revision = "010_add_auth_session_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("detection_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("frequency", sa.String(length=30), nullable=False),
        sa.Column("monthly_equivalent_amount", sa.Float(), nullable=False),
        sa.Column("last_payment_date", sa.Date(), nullable=False),
        sa.Column("next_expected_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("confidence_level", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("supporting_transaction_ids", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recurring_payments_user_id", "recurring_payments", ["user_id"])
    op.create_index(
        "ix_recurring_payments_user_detection_key",
        "recurring_payments",
        ["user_id", "detection_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_recurring_payments_user_detection_key", table_name="recurring_payments")
    op.drop_index("ix_recurring_payments_user_id", table_name="recurring_payments")
    op.drop_table("recurring_payments")
