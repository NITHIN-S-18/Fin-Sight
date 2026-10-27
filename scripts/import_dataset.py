from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.database.models.financial_profile import FinancialProfile
from app.database.models.transaction import Transaction
from app.database.models.user import User

DATA_DIR = BACKEND_ROOT / "app" / "data"
CSV_USERS = DATA_DIR / "users.csv"
CSV_TRANSACTIONS = DATA_DIR / "finsight_dataset_v2.csv"
CSV_PROFILES = DATA_DIR / "user_financial_profile.csv"

EXPECTED_COUNTS = {
    "users": 250,
    "transactions": 11365,
    "profiles": 250,
}

def _fail(message: str) -> None:
    print("IMPORT FAILED")
    print(message)
    raise SystemExit(1)


def _normalize_bool(value: object) -> bool | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"yes", "y", "true", "1"}:
            return True
        if text in {"no", "n", "false", "0"}:
            return False
        raise ValueError(f"Invalid boolean value: {value!r}")
    return bool(value)


def validate_required_columns(df: pd.DataFrame, required_columns: list[str], dataset_name: str) -> None:
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{dataset_name} is missing required columns: {missing}")


def load_users_csv() -> pd.DataFrame:
    if not CSV_USERS.exists():
        _fail(f"Missing users CSV: {CSV_USERS}")
    df = pd.read_csv(CSV_USERS)
    required = ["user_id", "persona", "income_type", "monthly_financial_capacity", "age_group", "city"]
    validate_required_columns(df, required, "users.csv")
    if df.empty:
        _fail("users.csv is empty")
    duplicate_ids = df[df["user_id"].duplicated(keep=False)]["user_id"].tolist()
    if duplicate_ids:
        raise ValueError(f"Duplicate user_id values found in users.csv: {duplicate_ids[:10]}")
    return df


def load_transactions_csv() -> pd.DataFrame:
    if not CSV_TRANSACTIONS.exists():
        _fail(f"Missing transaction CSV: {CSV_TRANSACTIONS}")
    df = pd.read_csv(CSV_TRANSACTIONS)
    required = [
        "transaction_id",
        "user_id",
        "transaction_date",
        "merchant_name",
        "description",
        "amount",
        "category",
        "transaction_class",
        "payment_mode",
        "frequency",
        "income_flag",
        "recurring_flag",
        "autopay_flag",
        "risk_label",
        "transaction_status",
        "is_new_subscription",
        "merchant_type",
        "commitment_type",
    ]
    validate_required_columns(df, required, "finsight_dataset_v2.csv")
    if df.empty:
        _fail("finsight_dataset_v2.csv is empty")
    duplicate_ids = df[df["transaction_id"].duplicated(keep=False)]["transaction_id"].tolist()
    if duplicate_ids:
        raise ValueError(f"Duplicate transaction_id values found in CSV: {duplicate_ids[:10]}")
    try:
        pd.to_datetime(df["transaction_date"], errors="raise")
    except Exception as exc:  # pragma: no cover - validation path
        raise ValueError(f"Invalid transaction_date values found in CSV: {exc}") from exc
    return df


def load_profiles_csv() -> pd.DataFrame:
    if not CSV_PROFILES.exists():
        _fail(f"Missing profile CSV: {CSV_PROFILES}")
    df = pd.read_csv(CSV_PROFILES)
    required = [
        "user_id",
        "persona",
        "monthly_financial_capacity",
        "monthly_commitments",
        "exposure_score",
        "active_subscriptions",
        "active_emis",
        "active_bnpl",
        "total_active_commitments",
        "total_transactions",
        "transaction_success_rate",
        "financial_health",
        "is_leakage_user",
        "leakage_subscription_count",
        "is_heavy_bnpl_user",
        "heavy_bnpl_providers",
        "is_heavy_emi_user",
        "heavy_emi_providers",
        "special_scenario",
    ]
    validate_required_columns(df, required, "user_financial_profile.csv")
    if df.empty:
        _fail("user_financial_profile.csv is empty")
    duplicate_ids = df[df["user_id"].duplicated(keep=False)]["user_id"].tolist()
    if duplicate_ids:
        raise ValueError(f"Duplicate user_id values found in profile CSV: {duplicate_ids[:10]}")
    return df


def _coerce_float(value: object, field_name: str) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {field_name}: {value!r}") from exc


def build_user_records(users_df: pd.DataFrame) -> list[User]:
    records: list[User] = []
    for row in users_df.to_dict(orient="records"):
        records.append(
            User(
                user_id=str(row["user_id"]),
                persona=str(row["persona"]),
                income_type=str(row["income_type"]),
                monthly_financial_capacity=_coerce_float(row.get("monthly_financial_capacity"), "monthly_financial_capacity"),
                age_group=str(row.get("age_group")) if pd.notna(row.get("age_group")) else None,
                city=str(row.get("city")) if pd.notna(row.get("city")) else None,
            )
        )
    return records


def build_transaction_records(transactions_df: pd.DataFrame) -> list[Transaction]:
    records: list[Transaction] = []
    for row in transactions_df.to_dict(orient="records"):
        records.append(
            Transaction(
                transaction_id=str(row["transaction_id"]),
                user_id=str(row["user_id"]),
                transaction_date=pd.to_datetime(row["transaction_date"]).to_pydatetime(),
                merchant_name=str(row.get("merchant_name")) if pd.notna(row.get("merchant_name")) else None,
                description=str(row.get("description")) if pd.notna(row.get("description")) else None,
                amount=_coerce_float(row["amount"], "amount"),
                category=str(row.get("category")) if pd.notna(row.get("category")) else None,
                transaction_class=str(row.get("transaction_class")) if pd.notna(row.get("transaction_class")) else None,
                payment_mode=str(row.get("payment_mode")) if pd.notna(row.get("payment_mode")) else None,
                frequency=str(row.get("frequency")) if pd.notna(row.get("frequency")) else None,
                income_flag=_normalize_bool(row.get("income_flag")),
                recurring_flag=_normalize_bool(row.get("recurring_flag")),
                autopay_flag=_normalize_bool(row.get("autopay_flag")),
                risk_label=str(row.get("risk_label")) if pd.notna(row.get("risk_label")) else None,
                transaction_status=str(row.get("transaction_status")) if pd.notna(row.get("transaction_status")) else None,
                is_new_subscription=_normalize_bool(row.get("is_new_subscription")),
                merchant_type=str(row.get("merchant_type")) if pd.notna(row.get("merchant_type")) else None,
                commitment_type=str(row.get("commitment_type")) if pd.notna(row.get("commitment_type")) else None,
            )
        )
    return records


def build_profile_records(profiles_df: pd.DataFrame) -> list[FinancialProfile]:
    records: list[FinancialProfile] = []

    for row in profiles_df.to_dict(orient="records"):
        records.append(
            FinancialProfile(
                user_id=str(row["user_id"]),
                monthly_income=_coerce_float(
                    row.get("monthly_income", row.get("monthly_financial_capacity")),
                    "monthly_income",
                ),
                financial_capacity=_coerce_float(
                    row.get("financial_capacity", row.get("monthly_financial_capacity")),
                    "financial_capacity",
                ),
                monthly_commitments=_coerce_float(
                    row.get("monthly_commitments"),
                    "monthly_commitments",
                ),
                subscription_burden=_coerce_float(
                    row.get("subscription_burden"),
                    "subscription_burden",
                ),
                emi_burden=_coerce_float(
                    row.get("emi_burden"),
                    "emi_burden",
                ),
                bnpl_burden=_coerce_float(
                    row.get("bnpl_burden"),
                    "bnpl_burden",
                ),
                exposure_score=_coerce_float(
                    row.get("exposure_score"),
                    "exposure_score",
                ),
                health_score=_coerce_float(
                    row.get("health_score"),
                    "health_score",
                ),
                risk_level=(
                    str(row.get("risk_level"))
                    if pd.notna(row.get("risk_level"))
                    else None
                ),

                persona=(
                    str(row.get("persona"))
                    if pd.notna(row.get("persona"))
                    else None
                ),
                active_subscriptions=int(row["active_subscriptions"]),
                active_emis=int(row["active_emis"]),
                active_bnpl=int(row["active_bnpl"]),
                total_active_commitments=int(row["total_active_commitments"]),
                total_transactions=int(row["total_transactions"]),
                transaction_success_rate=(
                    str(row["transaction_success_rate"])
                    if pd.notna(row["transaction_success_rate"])
                    else None
                ),
                financial_health=(
                    str(row["financial_health"])
                    if pd.notna(row["financial_health"])
                    else None
                ),
                is_leakage_user=(
                    str(row["is_leakage_user"])
                    if pd.notna(row["is_leakage_user"])
                    else None
                ),
                leakage_subscription_count=int(
                    row["leakage_subscription_count"]
                ),
                is_heavy_bnpl_user=(
                    str(row["is_heavy_bnpl_user"])
                    if pd.notna(row["is_heavy_bnpl_user"])
                    else None
                ),
                heavy_bnpl_providers=int(row["heavy_bnpl_providers"]),
                is_heavy_emi_user=(
                    str(row["is_heavy_emi_user"])
                    if pd.notna(row["is_heavy_emi_user"])
                    else None
                ),
                heavy_emi_providers=int(row["heavy_emi_providers"]),
                special_scenario=(
                    str(row["special_scenario"])
                    if pd.notna(row["special_scenario"])
                    else None
                ),
            )
        )

    return records


def count_db_rows(session) -> tuple[int, int, int]:
    user_count = session.query(User).count()
    transaction_count = session.query(Transaction).count()
    profile_count = session.query(FinancialProfile).count()
    return user_count, transaction_count, profile_count


def main() -> None:
    try:
        users_df = load_users_csv()
        transactions_df = load_transactions_csv()
        profiles_df = load_profiles_csv()

        csv_user_count = int(len(users_df))
        csv_transaction_count = int(len(transactions_df))
        csv_profile_count = int(len(profiles_df))

        if (
    csv_user_count != EXPECTED_COUNTS["users"]
    or csv_transaction_count != EXPECTED_COUNTS["transactions"]
    or csv_profile_count != EXPECTED_COUNTS["profiles"]
):
            _fail(
    "CSV counts do not match expected values: "
    f"users={csv_user_count} (expected {EXPECTED_COUNTS['users']}), "
    f"transactions={csv_transaction_count} (expected {EXPECTED_COUNTS['transactions']}), "
    f"profiles={csv_profile_count} (expected {EXPECTED_COUNTS['profiles']})"
)

        Base.metadata.create_all(bind=engine)

        user_rows = build_user_records(users_df)
        transaction_rows = build_transaction_records(transactions_df)
        profile_rows = build_profile_records(profiles_df)

        with SessionLocal() as session:
            session.query(FinancialProfile).delete()
            session.query(Transaction).delete()
            session.query(User).delete()
            session.add_all(user_rows)
            session.flush()
            session.add_all(transaction_rows)
            session.flush()
            session.add_all(profile_rows)
            session.commit()

        with SessionLocal() as session:
            db_user_count, db_transaction_count, db_profile_count = count_db_rows(session)

        print(
    f"CSV counts: {csv_user_count} users / "
    f"{csv_transaction_count} transactions / "
    f"{csv_profile_count} profiles"
)

        print(
    f"PostgreSQL counts: {db_user_count} users / "
    f"{db_transaction_count} transactions / "
    f"{db_profile_count} profiles"
)

        if (
    csv_user_count != db_user_count
    or csv_transaction_count != db_transaction_count
    or csv_profile_count != db_profile_count
): 
            _fail(
        "PostgreSQL counts do not match CSV counts: "
        f"users={db_user_count} vs {csv_user_count}, "
        f"transactions={db_transaction_count} vs {csv_transaction_count}, "
        f"profiles={db_profile_count} vs {csv_profile_count}"
    )

        print("IMPORT COMPLETE")
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - this is the loud failure path
        _fail(str(exc))


if __name__ == "__main__":
    main()
