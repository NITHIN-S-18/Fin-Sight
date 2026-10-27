"""create trial intelligence

Revision ID: 013_trial_intelligence
Revises: 012_manual_dates
"""

from alembic import op
import sqlalchemy as sa


revision = "013_trial_intelligence"
down_revision = "012_manual_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trial_intelligence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("merchant_name", sa.String(length=150), nullable=False),
        sa.Column("authorization_transaction_id", sa.String(length=100), nullable=False),
        sa.Column("authorization_amount", sa.Float(), nullable=False),
        sa.Column("authorization_date", sa.Date(), nullable=False),
        sa.Column("detected_state", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("possible_conversion_date", sa.Date(), nullable=True),
        sa.Column("related_recurring_payment_id", sa.Integer(), nullable=True),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("alert_sent_in_app", sa.Boolean(), nullable=False),
        sa.Column("alert_sent_email", sa.Boolean(), nullable=False),
        sa.Column("email_alert_scheduled_for", sa.DateTime(), nullable=True),
        sa.Column("email_alert_sent_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_recurring_payment_id"], ["recurring_payments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "authorization_transaction_id", name="uq_trial_user_authorization"),
    )
    op.create_index("ix_trial_intelligence_user_id", "trial_intelligence", ["user_id"])
    op.create_index(
        "ix_trial_intelligence_user_state",
        "trial_intelligence",
        ["user_id", "detected_state"],
    )
    op.create_index(
        "ix_trial_intelligence_email_due",
        "trial_intelligence",
        ["email_alert_scheduled_for", "alert_sent_email"],
    )


def downgrade() -> None:
    op.drop_index("ix_trial_intelligence_email_due", table_name="trial_intelligence")
    op.drop_index("ix_trial_intelligence_user_state", table_name="trial_intelligence")
    op.drop_index("ix_trial_intelligence_user_id", table_name="trial_intelligence")
    op.drop_table("trial_intelligence")
