"""add indexes and constraints

Revision ID: 004_add_indexes_and_constraints
Revises: 003_create_financial_profiles
Create Date: 2026-08-19 09:05:31.907000
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "004_add_indexes_and_constraints"
down_revision = "003_create_financial_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(op.f("ix_users_user_id"), "users", ["user_id"], unique=True)
    op.create_index(op.f("ix_transactions_transaction_id"), "transactions", ["transaction_id"], unique=True)
    op.create_index(op.f("ix_transactions_user_id"), "transactions", ["user_id"], unique=False)
    op.create_index(op.f("ix_transactions_transaction_date"), "transactions", ["transaction_date"], unique=False)
    op.create_index(op.f("ix_transactions_transaction_class"), "transactions", ["transaction_class"], unique=False)
    op.create_index(
        op.f("ix_transactions_user_id_transaction_date"),
        "transactions",
        ["user_id", "transaction_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_transactions_user_id_transaction_date"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_transaction_class"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_transaction_date"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_user_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_transaction_id"), table_name="transactions")
    op.drop_index(op.f("ix_users_user_id"), table_name="users")
