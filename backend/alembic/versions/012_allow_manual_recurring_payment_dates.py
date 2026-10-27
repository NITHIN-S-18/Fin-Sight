"""allow manual recurring payments without transaction dates

Revision ID: 012_allow_manual_recurring_payment_dates
Revises: 011_create_recurring_payments
"""

from alembic import op


revision = "012_manual_dates"
down_revision = "011_create_recurring_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("recurring_payments") as batch_op:
        batch_op.alter_column("last_payment_date", nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("recurring_payments") as batch_op:
        batch_op.alter_column("last_payment_date", nullable=False)
