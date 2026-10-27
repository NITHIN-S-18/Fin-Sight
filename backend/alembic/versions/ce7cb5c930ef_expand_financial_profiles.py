"""expand financial profiles

Revision ID: 005_expand_financial_profiles
Revises: 004_add_indexes_and_constraints
"""

from alembic import op
import sqlalchemy as sa

revision = "005_expand_financial_profiles"
down_revision = "004_add_indexes_and_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("financial_profiles", sa.Column("persona", sa.String(150), nullable=True))
    op.add_column("financial_profiles", sa.Column("active_subscriptions", sa.Integer(), nullable=True))
    op.add_column("financial_profiles", sa.Column("active_emis", sa.Integer(), nullable=True))
    op.add_column("financial_profiles", sa.Column("active_bnpl", sa.Integer(), nullable=True))
    op.add_column("financial_profiles", sa.Column("total_active_commitments", sa.Integer(), nullable=True))
    op.add_column("financial_profiles", sa.Column("total_transactions", sa.Integer(), nullable=True))
    op.add_column("financial_profiles", sa.Column("transaction_success_rate", sa.String(50), nullable=True))
    op.add_column("financial_profiles", sa.Column("financial_health", sa.String(100), nullable=True))
    op.add_column("financial_profiles", sa.Column("is_leakage_user", sa.String(20), nullable=True))
    op.add_column("financial_profiles", sa.Column("leakage_subscription_count", sa.Integer(), nullable=True))
    op.add_column("financial_profiles", sa.Column("is_heavy_bnpl_user", sa.String(20), nullable=True))
    op.add_column("financial_profiles", sa.Column("heavy_bnpl_providers", sa.Integer(), nullable=True))
    op.add_column("financial_profiles", sa.Column("is_heavy_emi_user", sa.String(20), nullable=True))
    op.add_column("financial_profiles", sa.Column("heavy_emi_providers", sa.Integer(), nullable=True))
    op.add_column("financial_profiles", sa.Column("special_scenario", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("financial_profiles", "special_scenario")
    op.drop_column("financial_profiles", "heavy_emi_providers")
    op.drop_column("financial_profiles", "is_heavy_emi_user")
    op.drop_column("financial_profiles", "heavy_bnpl_providers")
    op.drop_column("financial_profiles", "is_heavy_bnpl_user")
    op.drop_column("financial_profiles", "leakage_subscription_count")
    op.drop_column("financial_profiles", "is_leakage_user")
    op.drop_column("financial_profiles", "financial_health")
    op.drop_column("financial_profiles", "transaction_success_rate")
    op.drop_column("financial_profiles", "total_transactions")
    op.drop_column("financial_profiles", "total_active_commitments")
    op.drop_column("financial_profiles", "active_bnpl")
    op.drop_column("financial_profiles", "active_emis")
    op.drop_column("financial_profiles", "active_subscriptions")
    op.drop_column("financial_profiles", "persona")