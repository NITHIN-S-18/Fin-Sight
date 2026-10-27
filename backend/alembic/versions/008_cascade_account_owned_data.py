"""cascade deletion of account-owned data"""

from alembic import op


revision = "008_cascade_account_owned_data"
down_revision = "007_multi_user_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_auth_user_id", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_users_auth_user_id",
            "auth_users",
            ["auth_user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint("fk_transactions_user_id_users", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_transactions_user_id_users",
            "users",
            ["user_id"],
            ["user_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("transaction_imports") as batch_op:
        batch_op.drop_constraint("transaction_imports_auth_user_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "transaction_imports_auth_user_id_fkey",
            "auth_users",
            ["auth_user_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("transaction_imports") as batch_op:
        batch_op.drop_constraint("transaction_imports_auth_user_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "transaction_imports_auth_user_id_fkey",
            "auth_users",
            ["auth_user_id"],
            ["id"],
        )

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint("fk_transactions_user_id_users", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_transactions_user_id_users",
            "users",
            ["user_id"],
            ["user_id"],
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_auth_user_id", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_users_auth_user_id",
            "auth_users",
            ["auth_user_id"],
            ["id"],
        )
