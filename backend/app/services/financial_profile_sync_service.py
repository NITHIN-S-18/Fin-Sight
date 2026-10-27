from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.database.models.financial_profile import FinancialProfile
from app.database.models.transaction import Transaction
from app.database.models.user import User
from app.services.bnpl_service import BnplService
from app.services.commitment_service import UnifiedCommitmentService
from app.services.dataset_service import DatasetService
from app.services.emi_service import EmiService
from app.services.financial_rules import TransactionStatus, classify_transaction_status
from app.services.subscription_service import SubscriptionService


class FinancialProfileSyncService:
    """Projects an authenticated user's persisted transaction ledger into its profile."""

    def synchronize(
        self,
        session: Session,
        user: User,
        transactions: list[Transaction],
    ) -> FinancialProfile:
        transaction_records = [self._transaction_record(row) for row in transactions]

        subscription_service = SubscriptionService(None)  # type: ignore[arg-type]
        emi_service = EmiService(None)  # type: ignore[arg-type]
        bnpl_service = BnplService(None)  # type: ignore[arg-type]

        subscription_rows = self._active_rows(
            subscription_service,
            subscription_service._prepare_subscription_frame(transaction_records),
            "merchant_name",
            subscription_service._build_active_subscription,
        )
        emi_rows = self._active_rows(
            emi_service,
            emi_service._prepare_emi_frame(transaction_records),
            "merchant_name_normalized",
            emi_service._build_active_emi,
        )
        bnpl_rows = self._active_rows(
            bnpl_service,
            bnpl_service._prepare_bnpl_frame(transaction_records),
            "provider_name_normalized",
            bnpl_service._build_active_bnpl,
        )

        subscription_monthly = sum(row["monthly_estimated_cost"] for row in subscription_rows)
        emi_monthly = sum(row["monthly_emi_amount"] for row in emi_rows)
        bnpl_monthly = sum(row["monthly_bnpl_commitment"] for row in bnpl_rows)
        commitment_snapshot = UnifiedCommitmentService.snapshot_for_user(user.user_id, session)
        monthly_commitments = commitment_snapshot.total_monthly_commitments
        category_totals = commitment_snapshot.breakdown_by_category
        subscription_monthly = round(category_totals.get("subscription", 0.0), 2)
        emi_monthly = round(
            category_totals.get("emi", 0.0)
            + category_totals.get("loan", 0.0),
            2,
        )
        bnpl_monthly = round(category_totals.get("bnpl", 0.0), 2)
        monthly_capacity = DatasetService._infer_monthly_capacity(transactions) or 0.0
        exposure_score = round(monthly_commitments * 100.0 / monthly_capacity, 2) if monthly_capacity > 0 else 0.0

        profile = user.financial_profile
        if profile is None:
            profile = FinancialProfile(user=user)
            user.financial_profile = profile
            session.add(profile)

        profile.monthly_income = monthly_capacity
        profile.financial_capacity = monthly_capacity
        profile.persona = user.persona or "Authenticated User"
        profile.monthly_commitments = monthly_commitments
        profile.subscription_burden = round(subscription_monthly, 2)
        profile.emi_burden = round(emi_monthly, 2)
        profile.bnpl_burden = round(bnpl_monthly, 2)
        profile.exposure_score = exposure_score
        profile.active_subscriptions = sum(
            1 for item in commitment_snapshot.commitment_items if item.category.casefold() == "subscription"
        )
        profile.active_emis = sum(
            1 for item in commitment_snapshot.commitment_items if item.category.casefold() in {"emi", "loan"}
        )
        profile.active_bnpl = sum(
            1 for item in commitment_snapshot.commitment_items if item.category.casefold() == "bnpl"
        )
        profile.total_active_commitments = commitment_snapshot.active_commitment_count
        profile.total_transactions = len(transactions)
        profile.transaction_success_rate = self._success_rate(transactions)
        profile.financial_health = "Unknown"
        profile.is_leakage_user = "No"
        profile.leakage_subscription_count = 0
        profile.is_heavy_bnpl_user = "No"
        profile.heavy_bnpl_providers = 0
        profile.is_heavy_emi_user = "No"
        profile.heavy_emi_providers = 0
        profile.special_scenario = ""
        return profile

    @staticmethod
    def _active_rows(
        service: Any,
        frame: Any,
        group_column: str,
        builder: Any,
    ) -> list[dict[str, Any]]:
        if frame.empty:
            return []
        frame = frame.dropna(subset=["transaction_date"]).copy()
        if frame.empty:
            return []
        return [
            builder(service._normalize_text(group_name), group)
            for group_name, group in frame.groupby(group_column, dropna=False)
        ]

    @staticmethod
    def _transaction_record(row: Transaction) -> dict[str, Any]:
        return {
            "transaction_date": row.transaction_date,
            "merchant_name": row.merchant_name,
            "description": row.description,
            "amount": row.amount,
            "category": row.category,
            "transaction_class": row.transaction_class,
            "frequency": row.frequency,
            "autopay_flag": row.autopay_flag,
            "is_new_subscription": row.is_new_subscription,
            "merchant_type": row.merchant_type,
            "commitment_type": row.commitment_type,
            "transaction_status": row.transaction_status,
        }

    @staticmethod
    def _success_rate(transactions: list[Transaction]) -> str:
        if not transactions:
            return "0.0"
        successful = sum(
            1
            for row in transactions
            if classify_transaction_status(row.transaction_status) is TransactionStatus.SUCCESSFUL
        )
        return f"{round(successful * 100.0 / len(transactions), 2)}%"


def get_financial_profile_sync_service() -> FinancialProfileSyncService:
    return FinancialProfileSyncService()
