"""create transactions

Revision ID: 002_create_transactions
Revises: 001_create_users
Create Date: 2026-08-19 09:05:31.907000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_create_transactions"
down_revision = "001_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("transaction_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("transaction_date", sa.DateTime(), nullable=False),
        sa.Column("merchant_name", sa.String(length=150), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("transaction_class", sa.String(length=100), nullable=True),
        sa.Column("payment_mode", sa.String(length=100), nullable=True),
        sa.Column("frequency", sa.String(length=50), nullable=True),
        sa.Column("income_flag", sa.Boolean(), nullable=True),
        sa.Column("recurring_flag", sa.Boolean(), nullable=True),
        sa.Column("autopay_flag", sa.Boolean(), nullable=True),
        sa.Column("risk_label", sa.String(length=50), nullable=True),
        sa.Column("transaction_status", sa.String(length=50), nullable=True),
        sa.Column("is_new_subscription", sa.Boolean(), nullable=True),
        sa.Column("merchant_type", sa.String(length=100), nullable=True),
        sa.Column("commitment_type", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name="fk_transactions_user_id_users"),
        sa.UniqueConstraint("transaction_id", name="uq_transactions_transaction_id"),
    )


def downgrade() -> None:
    op.drop_table("transactions")
