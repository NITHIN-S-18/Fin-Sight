from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import DatasetLoadError, TransactionNotFoundError, UserNotFoundError
from app.database.connection import SessionLocal
from app.database.models.financial_profile import FinancialProfile
from app.database.models.transaction import Transaction
from app.database.models.user import User
from app.schemas.dataset import DatasetHealthResponse, DatasetSummaryResponse, DateRangeResponse

logger = logging.getLogger(__name__)
_request_cache: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar(
    "dataset_request_cache",
    default=None,
)


def begin_dataset_request_cache() -> Token:
    return _request_cache.set({"users": {}, "transactions": {}})


def end_dataset_request_cache(token: Token) -> None:
    _request_cache.reset(token)


class DatasetService:
    def __init__(self) -> None:
        self._loaded_at: pd.Timestamp | None = None
        self._loaded = False
        self._users_df = pd.DataFrame()
        self._transactions_df = pd.DataFrame()
        self._profiles_df = pd.DataFrame()
        self._load_all()

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def loaded_at(self) -> pd.Timestamp | None:
        return self._loaded_at

    @staticmethod
    def _users_dataframe(rows: list[User]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "user_id": row.user_id,
                    "persona": row.persona,
                    "income_type": row.income_type,
                    "monthly_financial_capacity": row.monthly_financial_capacity,
                    "age_group": row.age_group,
                    "city": row.city,
                }
                for row in rows
            ]
        )

    @staticmethod
    def _transactions_dataframe(rows: list[Transaction]) -> pd.DataFrame:
        dataframe = pd.DataFrame(
            [
                {
                    "transaction_id": row.transaction_id,
                    "user_id": row.user_id,
                    "transaction_date": row.transaction_date,
                    "merchant_name": row.merchant_name,
                    "description": row.description,
                    "amount": row.amount,
                    "category": row.category,
                    "transaction_class": row.transaction_class,
                    "payment_mode": row.payment_mode,
                    "frequency": row.frequency,
                    "income_flag": "Yes" if row.income_flag else "No" if row.income_flag is not None else None,
                    "recurring_flag": "Yes" if row.recurring_flag else "No" if row.recurring_flag is not None else None,
                    "autopay_flag": "Yes" if row.autopay_flag else "No" if row.autopay_flag is not None else None,
                    "risk_label": row.risk_label,
                    "transaction_status": row.transaction_status,
                    "is_new_subscription": "Yes" if row.is_new_subscription else "No" if row.is_new_subscription is not None else None,
                    "merchant_type": row.merchant_type,
                    "commitment_type": row.commitment_type,
                }
                for row in rows
            ]
        )
        if not dataframe.empty:
            commitment_classes = {"subscription", "emi", "bnpl"}
            category_values = dataframe["category"].fillna("").astype(str).str.strip().str.lower()
            class_values = dataframe["transaction_class"].fillna("").astype(str).str.strip().str.lower()
            dataframe.loc[category_values.isin(commitment_classes), "transaction_class"] = (
                category_values[category_values.isin(commitment_classes)].str.title()
            )
            dataframe.loc[class_values.isin(commitment_classes), "transaction_class"] = (
                class_values[class_values.isin(commitment_classes)].str.title()
            )
        return dataframe

    @staticmethod
    def _infer_monthly_capacity(transactions: list[Transaction]) -> float | None:
        income_rows = []
        for row in transactions:
            category = (row.category or "").strip().lower()
            transaction_class = (row.transaction_class or "").strip().lower()
            if category == "income" or transaction_class in {"income", "salary"} or row.income_flag:
                income_rows.append(row)
        if not income_rows:
            return None

        monthly_totals: dict[tuple[int, int], float] = {}
        for row in income_rows:
            period = (row.transaction_date.year, row.transaction_date.month)
            monthly_totals[period] = monthly_totals.get(period, 0.0) + max(float(row.amount), 0.0)
        return round(sum(monthly_totals.values()) / len(monthly_totals), 2)

    @staticmethod
    def _profiles_dataframe(rows: list[FinancialProfile]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "user_id": row.user_id,
                    "persona": row.persona,
                    "monthly_financial_capacity": row.financial_capacity,
                    "monthly_commitments": row.monthly_commitments,
                    "exposure_score": row.exposure_score,
                    "active_subscriptions": row.active_subscriptions,
                    "active_emis": row.active_emis,
                    "active_bnpl": row.active_bnpl,
                    "total_active_commitments": row.total_active_commitments,
                    "total_transactions": row.total_transactions,
                    "transaction_success_rate": row.transaction_success_rate,
                    "financial_health": row.financial_health,
                    "is_leakage_user": row.is_leakage_user,
                    "leakage_subscription_count": row.leakage_subscription_count,
                    "is_heavy_bnpl_user": row.is_heavy_bnpl_user,
                    "heavy_bnpl_providers": row.heavy_bnpl_providers,
                    "is_heavy_emi_user": row.is_heavy_emi_user,
                    "heavy_emi_providers": row.heavy_emi_providers,
                    "special_scenario": row.special_scenario,
                }
                for row in rows
            ]
        )

    def _load_all(self) -> None:
        if get_settings().data_source.lower() == "csv":
            self._load_from_csv()
            return

        self._load_from_postgres()

    def _load_from_csv(self) -> None:
        logger.info("Loading FinSight reference datasets from CSV")
        data_directory = Path(__file__).resolve().parents[1] / "data"

        try:
            users = pd.read_csv(data_directory / "users.csv")
            transactions = pd.read_csv(data_directory / "finsight_dataset_v2.csv")
            profiles = pd.read_csv(data_directory / "user_financial_profile.csv")

            required_files = {
                "users": users,
                "transactions": transactions,
                "profiles": profiles,
            }
            for name, dataframe in required_files.items():
                if dataframe.empty:
                    raise DatasetLoadError(f"CSV reference dataset is empty: {name}")

            self._users_df = users
            self._transactions_df = self._transactions_dataframe_from_csv(transactions)
            self._profiles_df = profiles

            self._transactions_df["transaction_date"] = pd.to_datetime(
                self._transactions_df["transaction_date"],
                errors="coerce",
            )
            if self._transactions_df["transaction_date"].isna().any():
                raise DatasetLoadError("CSV contains invalid transaction_date values.")

            self._loaded_at = pd.Timestamp.now("UTC")
            self._loaded = True
            logger.info(
                "Loaded FinSight reference datasets from CSV: users=%s transactions=%s profiles=%s",
                len(self._users_df),
                len(self._transactions_df),
                len(self._profiles_df),
            )
        except DatasetLoadError:
            raise
        except (OSError, pd.errors.ParserError, ValueError) as exc:
            raise DatasetLoadError(f"Unable to load CSV reference datasets: {exc}") from exc

    @classmethod
    def _transactions_dataframe_from_csv(cls, dataframe: pd.DataFrame) -> pd.DataFrame:
        normalized = dataframe.copy()
        for column in (
            "income_flag",
            "recurring_flag",
            "autopay_flag",
            "is_new_subscription",
        ):
            if column in normalized.columns:
                normalized[column] = normalized[column].where(
                    normalized[column].notna(),
                    None,
                )
        return cls._transactions_dataframe_from_records(normalized)

    @staticmethod
    def _transactions_dataframe_from_records(dataframe: pd.DataFrame) -> pd.DataFrame:
        normalized = dataframe.copy()
        commitment_classes = {"subscription", "emi", "bnpl"}
        if "category" in normalized.columns and "transaction_class" in normalized.columns:
            category_values = normalized["category"].fillna("").astype(str).str.strip().str.lower()
            class_values = normalized["transaction_class"].fillna("").astype(str).str.strip().str.lower()
            normalized.loc[category_values.isin(commitment_classes), "transaction_class"] = (
                category_values[category_values.isin(commitment_classes)].str.title()
            )
            normalized.loc[class_values.isin(commitment_classes), "transaction_class"] = (
                class_values[class_values.isin(commitment_classes)].str.title()
            )
        return normalized

    def _load_from_postgres(self) -> None:
        logger.info("Loading FinSight datasets from PostgreSQL")

        try:
            with SessionLocal() as session:
                users = session.execute(
                    select(User).where(User.auth_user_id.is_(None))
                ).scalars().all()
                transactions = session.execute(
                    select(Transaction)
                    .join(User, Transaction.user_id == User.user_id)
                    .where(User.auth_user_id.is_(None))
                ).scalars().all()
                profiles = session.execute(
                    select(FinancialProfile)
                    .join(User, FinancialProfile.user_id == User.user_id)
                    .where(User.auth_user_id.is_(None))
                ).scalars().all()

            if not users:
                raise DatasetLoadError("No users found in PostgreSQL.")
            if not transactions:
                raise DatasetLoadError("No transactions found in PostgreSQL.")
            if not profiles:
                raise DatasetLoadError("No financial profiles found in PostgreSQL.")

            self._users_df = self._users_dataframe(users)
            self._transactions_df = self._transactions_dataframe(transactions)
            self._profiles_df = self._profiles_dataframe(profiles)

            self._transactions_df["transaction_date"] = pd.to_datetime(
                self._transactions_df["transaction_date"],
                errors="coerce",
            )

            if self._transactions_df["transaction_date"].isna().any():
                raise DatasetLoadError(
                    "PostgreSQL contains invalid transaction_date values."
                )

            self._loaded_at = pd.Timestamp.now("UTC")
            self._loaded = True

            logger.info(
                "Loaded FinSight datasets from PostgreSQL: users=%s transactions=%s profiles=%s",
                len(self._users_df),
                len(self._transactions_df),
                len(self._profiles_df),
            )

        except DatasetLoadError:
            raise
        except Exception as exc:
            raise DatasetLoadError(
                f"Unable to load datasets from PostgreSQL: {exc}"
            ) from exc

    @staticmethod
    def _frame_to_records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        if dataframe.empty:
            return []

        normalized = dataframe.copy()

        for column in normalized.columns:
            if pd.api.types.is_datetime64_any_dtype(normalized[column]):
                normalized[column] = normalized[column].dt.date

        records = normalized.to_dict(orient="records")
        return [
            {key: (None if pd.isna(value) else value) for key, value in record.items()}
            for record in records
        ]

    @staticmethod
    def _row_to_dict(row: pd.Series) -> dict[str, Any]:
        record = row.to_dict()

        for key, value in list(record.items()):
            if isinstance(value, pd.Timestamp):
                record[key] = value.date()

        return record

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            raise DatasetLoadError("Dataset service is not loaded.")

    def _get_user_row(self, user_id: str) -> pd.Series:
        matches = self._users_df[self._users_df["user_id"] == user_id]

        if matches.empty:
            raise UserNotFoundError(f"User not found: {user_id}")

        return matches.iloc[0]

    def _get_transaction_row(self, transaction_id: str) -> pd.Series:
        matches = self._transactions_df[
            self._transactions_df["transaction_id"] == transaction_id
        ]

        if matches.empty:
            raise TransactionNotFoundError(
                f"Transaction not found: {transaction_id}"
            )

        return matches.iloc[0]

    def get_summary(self) -> DatasetSummaryResponse:
        self._ensure_loaded()

        transaction_dates = self._transactions_df["transaction_date"]

        distribution = lambda column: {
            str(index): int(value)
            for index, value in self._transactions_df[column]
            .value_counts(dropna=False)
            .sort_index()
            .items()
        }

        persona_distribution = {
            str(index): int(value)
            for index, value in self._users_df["persona"]
            .value_counts(dropna=False)
            .sort_index()
            .items()
        }

        return DatasetSummaryResponse(
            total_users=int(len(self._users_df)),
            total_transactions=int(len(self._transactions_df)),
            date_range=DateRangeResponse(
                start_date=transaction_dates.min().date(),
                end_date=transaction_dates.max().date(),
            ),
            persona_distribution=persona_distribution,
            transaction_class_distribution=distribution("transaction_class"),
            risk_distribution=distribution("risk_label"),
            autopay_distribution=distribution("autopay_flag"),
        )

    def get_all_users(self) -> list[dict[str, Any]]:
        self._ensure_loaded()
        return self._frame_to_records(self._users_df)

    def get_user(self, user_id: str) -> dict[str, Any]:
        self._ensure_loaded()

        cache = _request_cache.get()
        cached_user = cache["users"].get(user_id) if cache is not None else None
        if cached_user is not None:
            return dict(cached_user)

        if get_settings().data_source.lower() != "csv" or user_id.startswith("AUTH"):
            with SessionLocal() as session:
                database_user = session.execute(
                    select(User).where(User.user_id == user_id)
                ).scalar_one_or_none()
                if database_user is not None:
                    user_transactions = session.execute(
                        select(Transaction).where(Transaction.user_id == user_id)
                    ).scalars().all()
                    monthly_capacity = database_user.monthly_financial_capacity
                    if monthly_capacity is None:
                        monthly_capacity = self._infer_monthly_capacity(user_transactions)
                    record = {
                        "user_id": database_user.user_id,
                        "persona": database_user.persona,
                        "income_type": database_user.income_type,
                        "monthly_financial_capacity": monthly_capacity,
                        "age_group": database_user.age_group,
                        "city": database_user.city,
                        "financial_profile": None,
                    }
                    if database_user.financial_profile is not None:
                        record["financial_profile"] = self._profiles_dataframe(
                            [database_user.financial_profile]
                        ).iloc[0].to_dict()
                    if cache is not None:
                        cache["users"][user_id] = record
                        cache["transactions"][user_id] = self._frame_to_records(
                            self._transactions_dataframe(user_transactions)
                        )
                    return record

        user_row = self._get_user_row(user_id)
        user_record = self._row_to_dict(user_row)

        profile_matches = self._profiles_df[
            self._profiles_df["user_id"] == user_id
        ]

        user_record["financial_profile"] = (
            self._row_to_dict(profile_matches.iloc[0])
            if not profile_matches.empty
            else None
        )
        if cache is not None:
            cache["users"][user_id] = user_record

        return user_record

    def get_all_transactions(self) -> list[dict[str, Any]]:
        self._ensure_loaded()
        return self._frame_to_records(self._transactions_df)

    def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        self._ensure_loaded()

        with SessionLocal() as session:
            database_transaction = session.execute(
                select(Transaction).where(Transaction.transaction_id == transaction_id)
            ).scalar_one_or_none()
            if database_transaction is not None:
                return self._row_to_dict(
                    self._transactions_dataframe([database_transaction]).iloc[0]
                )

        return self._row_to_dict(
            self._get_transaction_row(transaction_id)
        )

    def get_user_transactions(self, user_id: str) -> list[dict[str, Any]]:
        self._ensure_loaded()

        cache = _request_cache.get()
        cached_transactions = cache["transactions"].get(user_id) if cache is not None else None
        if cached_transactions is not None:
            return [dict(transaction) for transaction in cached_transactions]

        if get_settings().data_source.lower() != "csv" or user_id.startswith("AUTH"):
            with SessionLocal() as session:
                database_user = session.execute(
                    select(User).where(User.user_id == user_id)
                ).scalar_one_or_none()
                if database_user is not None:
                    rows = session.execute(
                        select(Transaction).where(Transaction.user_id == user_id)
                    ).scalars().all()
                    transactions = self._frame_to_records(self._transactions_dataframe(rows))
                    if cache is not None:
                        cache["transactions"][user_id] = transactions
                    return [dict(transaction) for transaction in transactions]

        self._get_user_row(user_id)

        user_transactions = self._transactions_df[
            self._transactions_df["user_id"] == user_id
        ]

        transactions = self._frame_to_records(user_transactions)
        if cache is not None:
            cache["transactions"][user_id] = transactions
        return [dict(transaction) for transaction in transactions]

    def get_health(self) -> DatasetHealthResponse:
        self._ensure_loaded()

        return DatasetHealthResponse(
            status="ok",
            loaded=self._loaded,
            loaded_at=(
                self._loaded_at.to_pydatetime()
                if self._loaded_at is not None
                else None
            ),
            records={
                "users": int(len(self._users_df)),
                "transactions": int(len(self._transactions_df)),
                "user_profiles": int(len(self._profiles_df)),
            },
        )


@lru_cache(maxsize=1)
def get_dataset_service() -> DatasetService:
    return DatasetService()


def invalidate_dataset_service_cache() -> None:
    """Force the next request to load the committed database state."""
    get_dataset_service.cache_clear()
    try:
        from app.services.exposure_service import get_exposure_service
        get_exposure_service.cache_clear()
    except Exception:
        pass
    try:
        from app.services.ml_service import get_ml_service
        get_ml_service.cache_clear()
    except Exception:
        pass
    try:
        from app.services.dashboard_service import get_dashboard_service
        get_dashboard_service.cache_clear()
    except Exception:
        pass
    try:
        from app.services.cashflow_forecast_service import get_cashflow_forecast_service
        get_cashflow_forecast_service.cache_clear()
    except Exception:
        pass
    try:
        from app.services.shortfall_service import get_shortfall_service
        get_shortfall_service.cache_clear()
    except Exception:
        pass
    try:
        from app.services.commitment_service import get_unified_commitment_service
        get_unified_commitment_service.cache_clear()
    except Exception:
        pass