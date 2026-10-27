"""link auth accounts to financial users and add import metadata"""

from alembic import op
import sqlalchemy as sa


revision = "007_multi_user_ingestion"
down_revision = "006_create_auth_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("persona", existing_type=sa.String(length=150), nullable=True)
        batch_op.add_column(sa.Column("auth_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_auth_user_id",
            "auth_users",
            ["auth_user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(op.f("ix_users_auth_user_id"), ["auth_user_id"], unique=True)
    op.add_column("transactions", sa.Column("import_fingerprint", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_transactions_import_fingerprint"), "transactions", ["import_fingerprint"], unique=False)
    op.create_table(
        "transaction_imports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "auth_user_id",
            sa.Integer(),
            sa.ForeignKey(
                "auth_users.id",
                name="transaction_imports_auth_user_id_fkey",
            ),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("transaction_start_date", sa.DateTime(), nullable=True),
        sa.Column("transaction_end_date", sa.DateTime(), nullable=True),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
    )
    op.create_index(op.f("ix_transaction_imports_auth_user_id"), "transaction_imports", ["auth_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_transaction_imports_auth_user_id"), table_name="transaction_imports")
    op.drop_table("transaction_imports")
    op.drop_index(op.f("ix_transactions_import_fingerprint"), table_name="transactions")
    op.drop_column("transactions", "import_fingerprint")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_auth_user_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_users_auth_user_id"))
        batch_op.drop_column("auth_user_id")
        batch_op.alter_column("persona", existing_type=sa.String(length=150), nullable=False)