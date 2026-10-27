from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import HTTPException, status
from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.user import User
from app.database.models.user_income_configuration import UserIncomeConfiguration
from app.schemas.income import (
    IncomeConfigurationResponse,
    IncomeConfigurationUpdateRequest,
)

logger = logging.getLogger(__name__)


class IncomeService:
    def __init__(self) -> None:
        pass

    def get_user_income_config(self, user_id: str) -> UserIncomeConfiguration | None:
        with SessionLocal() as session:
            return session.execute(
                select(UserIncomeConfiguration).where(UserIncomeConfiguration.user_id == user_id)
            ).scalar_one_or_none()

    def resolve_effective_income(
        self,
        user_id: str,
        auto_detected_income: float,
    ) -> tuple[float, str, str, float | None, float | None]:
        """
        Resolves effective monthly income and source metadata according to precedence rules:
        - Mode 'manual': if manual_monthly_income is set and > 0, returns (manual_monthly_income, 'Manual', 'manual', expected, manual)
        - Mode 'expected': returns (auto_detected_income, 'Observed', 'expected', expected, manual)
          (Expected income is used for planning/simulations, preserving current income reality)
        - Mode 'auto': returns (auto_detected_income, 'Observed' if auto_detected_income > 0 else 'Estimated', 'auto', expected, manual)
        """
        config = self.get_user_income_config(user_id)
        if config is None:
            source = "Observed" if auto_detected_income > 0 else "Estimated"
            return auto_detected_income, source, "auto", None, None

        income_mode = config.income_mode or "auto"
        expected = config.expected_monthly_income
        manual = config.manual_monthly_income

        if income_mode == "manual" and manual is not None and manual > 0:
            return manual, "Manual", "manual", expected, manual

        # In 'expected' mode or 'auto' mode or if manual <= 0:
        source = "Observed" if auto_detected_income > 0 else "Estimated"
        return auto_detected_income, source, income_mode, expected, manual

    def get_auto_detected_income(self, user_id: str) -> float:
        try:
            from app.services.dataset_service import get_dataset_service
            dataset_service = get_dataset_service()
            user_record = dataset_service.get_user(user_id)
            capacity = float(user_record.get("monthly_financial_capacity") or 0.0)
            if capacity <= 0 and user_record.get("financial_profile"):
                capacity = float(user_record["financial_profile"].get("monthly_financial_capacity") or 0.0)
            if capacity <= 0:
                txs = dataset_service.get_user_transactions(user_id)
                if txs:
                    import pandas as pd
                    frame = pd.DataFrame(txs)
                    if not frame.empty and "category" in frame.columns:
                        income_txs = frame[
                            (frame["category"].astype(str).str.lower() == "income")
                            | (frame.get("transaction_class", pd.Series()).astype(str).str.lower().isin(["income", "salary"]))
                            | (frame.get("income_flag", pd.Series()).astype(str).str.lower().isin(["yes", "true", "1"]))
                        ]
                        if not income_txs.empty and "transaction_date" in income_txs.columns and "amount" in income_txs.columns:
                            dt_series = pd.to_datetime(income_txs["transaction_date"], errors="coerce")
                            periods = dt_series.dt.to_period("M")
                            amounts = pd.to_numeric(income_txs["amount"], errors="coerce").fillna(0.0)
                            month_sums = amounts.groupby(periods).sum()
                            if not month_sums.empty:
                                capacity = round(float(month_sums.mean()), 2)
            return round(capacity, 2)
        except Exception:
            return 0.0

    def get_income_configuration_response(
        self,
        user_id: str,
        auto_detected_income: float = 0.0,
    ) -> IncomeConfigurationResponse:
        if auto_detected_income <= 0:
            auto_detected_income = self.get_auto_detected_income(user_id)

        effective, source_label, mode, expected, manual = self.resolve_effective_income(
            user_id, auto_detected_income
        )
        config = self.get_user_income_config(user_id)
        return IncomeConfigurationResponse(
            user_id=user_id,
            income_mode=mode,  # type: ignore[arg-type]
            manual_monthly_income=manual,
            expected_monthly_income=expected,
            effective_date=config.effective_date if config else None,
            effective_monthly_income=effective,
            income_source_label=source_label,  # type: ignore[arg-type]
            auto_detected_income=auto_detected_income,
            created_at=config.created_at if config else None,
            updated_at=config.updated_at if config else None,
        )

    def update_income_configuration(
        self,
        user_id: str,
        request: IncomeConfigurationUpdateRequest,
        auto_detected_income: float = 0.0,
    ) -> IncomeConfigurationResponse:
        if request.income_mode == "manual":
            if request.manual_monthly_income is None or request.manual_monthly_income <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A valid monthly income greater than 0 must be provided when mode is manual.",
                )
        elif request.income_mode == "expected":
            if request.expected_monthly_income is None or request.expected_monthly_income <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A valid expected future income greater than 0 must be provided when mode is expected.",
                )

        with SessionLocal() as session:
            user = session.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()
            if user is None:
                user = User(user_id=user_id)
                session.add(user)
                session.flush()

            config = session.execute(
                select(UserIncomeConfiguration).where(UserIncomeConfiguration.user_id == user_id)
            ).scalar_one_or_none()

            now = datetime.now(timezone.utc)
            if config is None:
                config = UserIncomeConfiguration(
                    user_id=user_id,
                    income_mode=request.income_mode,
                    manual_monthly_income=request.manual_monthly_income,
                    expected_monthly_income=request.expected_monthly_income,
                    effective_date=request.effective_date,
                    created_at=now,
                    updated_at=now,
                )
                session.add(config)
            else:
                config.income_mode = request.income_mode
                if request.manual_monthly_income is not None or request.income_mode == "manual":
                    config.manual_monthly_income = request.manual_monthly_income
                if request.expected_monthly_income is not None or request.income_mode == "expected":
                    config.expected_monthly_income = request.expected_monthly_income
                config.effective_date = request.effective_date
                config.updated_at = now

            session.commit()
            session.refresh(config)

        logger.info(
            "User income configuration updated for user_id=%s mode=%s manual=%s expected=%s",
            user_id,
            request.income_mode,
            request.manual_monthly_income,
            request.expected_monthly_income,
        )

        return self.get_income_configuration_response(user_id, auto_detected_income)


@lru_cache(maxsize=1)
def get_income_service() -> IncomeService:
    return IncomeService()
