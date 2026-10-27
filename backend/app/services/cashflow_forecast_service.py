from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

import pandas as pd

from app.core.exceptions import ExposureDataUnavailableError
from app.ml.cashflow_forecast import CashFlowForecastDatasetBuilder, CashFlowModelTrainer, evaluate_baselines
from app.ml.persistence import ModelPersistenceManager
from app.schemas.forecast import CashFlowForecastResponse, ForecastTargetMetrics
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.financial_rules import TransactionStatus, classify_transaction_status


class CashFlowForecastService:
    def __init__(self, dataset_service: DatasetService) -> None:
        self._dataset_service = dataset_service
        self._builder = CashFlowForecastDatasetBuilder()
        self._persistence = ModelPersistenceManager()

    def forecast(self, user_id: str) -> CashFlowForecastResponse:
        transactions = self._dataset_service.get_user_transactions(user_id)
        frame = pd.DataFrame(transactions)
        monthly = self._builder.monthly_series(frame)
        if monthly.empty:
            raise ExposureDataUnavailableError(f"No transaction history available for user: {user_id}")
        history_months = len(monthly)
        forecast_month = str(monthly.index.max() + 1)
        if history_months < self._builder.minimum_history_months:
            return CashFlowForecastResponse(
                user_id=user_id,
                forecast_month=forecast_month,
                forecast_available=False,
                availability_status="insufficient_history",
                history_months_available=history_months,
                expected_income=None,
                expected_committed_expenses=None,
                expected_variable_expenses=None,
                expected_total_expenses=None,
                expected_net_cash=None,
                model_version="unavailable",
                model_type="none",
                data_cutoff=str(monthly.index.max()),
                generated_at=datetime.now(timezone.utc),
            )

        examples = self._builder.build(frame)
        reports, selected = evaluate_baselines(examples)
        selected = {
            "income": "six_month_average",
            "committed": "three_month_average",
            "variable": "six_month_average",
            **selected,
        }
        values: dict[str, float] = {}
        for target, name in selected.items():
            window = {"previous_month": 1, "three_month_average": 3, "six_month_average": 6}[name]
            values[target] = round(float(monthly[target].tail(window).mean()), 2)
        model_version = "baseline-v1"
        model_type = "rolling-baseline"
        evaluation = {
            target: ForecastTargetMetrics(**metrics)
            for target, metrics in reports.items()
            if target != "_split"
        }
        split_metadata = reports.get("_split", {})
        try:
            bundle = self._persistence.load("cash_flow_forecast", "v1.0")
            current = self._builder.current_example(frame)
            if current is not None:
                model_values = CashFlowModelTrainer.predict(bundle, current)
                selected_forecasters = bundle.artifact.metadata.get("selected_forecasters", {})
                for target, forecaster in selected_forecasters.items():
                    if forecaster == "ml":
                        values[target] = model_values[target]
                model_version = bundle.artifact.model_version
                model_type = "accepted-hybrid"
                test_metadata = bundle.artifact.metadata.get("test", {})
                evaluation = {
                    target: ForecastTargetMetrics(
                        **{
                            "mae": metrics["selected_metrics"]["mae"],
                            "rmse": metrics["selected_metrics"]["rmse"],
                            "r2": metrics["selected_metrics"]["r2"],
                            "median_absolute_error": metrics["selected_metrics"]["median_absolute_error"],
                            "percentile_90_absolute_error": metrics["selected_metrics"]["p90_absolute_error"],
                        }
                    )
                    for target, metrics in test_metadata.items()
                }
                split_metadata = bundle.artifact.metadata.get("split", {})
        except FileNotFoundError:
            pass
        # Authoritative commitment and manual income alignment for prospective forecast:
        from app.services.commitment_service import UnifiedCommitmentService
        from app.services.income_service import IncomeService

        commitment_snapshot = UnifiedCommitmentService.snapshot_for_user(user_id)
        if commitment_snapshot.total_monthly_commitments > 0:
            values["committed"] = round(float(commitment_snapshot.total_monthly_commitments), 2)

        income_service = IncomeService()
        effective_income, _, mode, _, _ = income_service.resolve_effective_income(user_id, values["income"])
        if mode == "manual" and effective_income > 0:
            values["income"] = round(float(effective_income), 2)

        total = round(values["committed"] + values["variable"], 2)
        variable_category_forecast = self._variable_category_forecast(
            frame, expected_variable_expenses=values["variable"]
        )
        return CashFlowForecastResponse(
            user_id=user_id,
            forecast_month=forecast_month,
            forecast_available=True,
            availability_status="available",
            history_months_available=history_months,
            expected_income=values["income"],
            expected_committed_expenses=values["committed"],
            expected_variable_expenses=values["variable"],
            expected_total_expenses=total,
            expected_net_cash=round(values["income"] - total, 2),
            selected_baselines=selected,
            model_version=model_version,
            model_type=model_type,
            data_cutoff=str(monthly.index.max()),
            variable_category_forecast=variable_category_forecast,
            evaluation=evaluation,
            split_metadata=split_metadata,
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _variable_category_forecast(
        frame: pd.DataFrame, *, expected_variable_expenses: float
    ) -> dict[str, float]:
        """Allocate Model 1's monthly variable forecast by supported category shares.

        Category amounts are not separately trained predictions.  They are
        historical, successful-transaction proportions applied to the already
        selected Model 1 total, so their sum has the same period and scope as
        ``expected_variable_expenses``.  Categories with fewer than two
        observed months are omitted rather than treated as a forecast.
        """
        if frame.empty or "category" not in frame.columns or expected_variable_expenses < 0:
            return {}
        rows = frame.copy()
        rows["amount"] = pd.to_numeric(rows["amount"], errors="coerce").fillna(0.0)
        rows["month"] = pd.to_datetime(rows["transaction_date"], errors="coerce").dt.to_period("M")
        classes = rows["transaction_class"] if "transaction_class" in rows else pd.Series("", index=rows.index)
        income_flags = rows["income_flag"] if "income_flag" in rows else pd.Series(False, index=rows.index)
        statuses = rows["transaction_status"] if "transaction_status" in rows else pd.Series("", index=rows.index)
        rows["class"] = classes.fillna("").astype(str).str.lower()
        rows["income"] = income_flags.fillna(False).astype(str).str.lower().isin({"yes", "true", "1"})
        successful = statuses.fillna("").map(classify_transaction_status).eq(TransactionStatus.SUCCESSFUL)
        eligible = successful & rows["amount"].gt(0) & ~rows["income"] & ~rows["class"].isin({"subscription", "emi", "bnpl"})
        recent = rows.loc[eligible & rows["month"].ge(rows["month"].max() - 5)]
        if recent.empty:
            return {}
        monthly = recent.groupby(["category", "month"])["amount"].sum()
        category_levels: dict[str, float] = {}
        for category, values in monthly.groupby(level=0):
            series = values.droplevel(0)
            if series.index.nunique() < 2:
                continue
            median = float(series.median())
            if median > 0:
                category_levels[str(category)] = median
        total_level = sum(category_levels.values())
        if total_level <= 0:
            return {}
        allocated: dict[str, float] = {}
        remaining = round(float(expected_variable_expenses), 2)
        items = sorted(category_levels.items(), key=lambda item: item[1], reverse=True)
        for category, level in items[:-1]:
            amount = round(float(expected_variable_expenses) * level / total_level, 2)
            allocated[category] = amount
            remaining = round(remaining - amount, 2)
        if items:
            allocated[items[-1][0]] = max(remaining, 0.0)
        return allocated


@lru_cache(maxsize=1)
def get_cashflow_forecast_service() -> CashFlowForecastService:
    return CashFlowForecastService(get_dataset_service())
