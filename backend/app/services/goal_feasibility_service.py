from __future__ import annotations

import pickle
from datetime import datetime, timezone
from functools import lru_cache
from math import ceil, isfinite
from pathlib import Path
from typing import Any

import pandas as pd

from app.database.connection import SessionLocal
from app.database.models.financial_goal import FinancialGoal
from app.schemas.goals import (
    CategoryAdjustment,
    FinancialGoalResponse,
    GoalCreateRequest,
    GoalEvaluation,
    GoalRequest,
    GoalUpdateRequest,
)
from app.services.cashflow_forecast_service import (
    CashFlowForecastService,
    get_cashflow_forecast_service,
)
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.financial_rules import TransactionStatus, classify_transaction_status
from app.ml.goal_feasibility import FEATURE_COLUMNS


class GoalFeasibilityService:
    """Model 2 orchestration over the frozen Model 1 forecast."""

    DISCRETIONARY_POLICY_TRIMMING_LIMIT = 0.35
    _protected_tokens = {
        "rent",
        "electricity",
        "water",
        "utility",
        "utilities",
        "internet",
        "insurance",
        "medical",
        "healthcare",
        "education",
        "loan",
        "emi",
        "bnpl",
        "subscription",
        "grocery",
        "groceries",
        "medicine",
        "pharmacy",
    }
    _adjustable_tokens = {
        "dining", "restaurant", "food delivery", "takeaway", "shopping",
        "apparel", "clothing", "entertainment", "leisure", "travel",
    }

    def __init__(
        self,
        dataset_service: DatasetService,
        forecast_service: CashFlowForecastService,
    ) -> None:
        self._dataset_service = dataset_service
        self._forecast_service = forecast_service
        self._model = self._load_model()

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_model() -> Any | None:
        path = (
            Path(__file__).resolve().parents[1]
            / "ml"
            / "saved_models"
            / "goal_feasibility"
            / "model-2-phase-c-v2.pkl"
        )
        if not path.exists():
            return None
        try:
            with path.open("rb") as handle:
                payload = pickle.load(handle)
            return payload.get("model") if isinstance(payload, dict) else None
        except (OSError, pickle.PickleError, EOFError, AttributeError, TypeError):
            return None

    @staticmethod
    def _money(value: float | None) -> float | None:
        return None if value is None else round(float(value), 2)

    @classmethod
    def _is_protected(cls, category: object, transaction_class: object = "") -> bool:
        value = f"{category or ''} {transaction_class or ''}".strip().lower()
        if value in {"food delivery", "takeaway", "dining", "restaurant"}:
            return False
        if value in {"food", "transport"} or "grocer" in value:
            return True
        return any(token in value for token in cls._protected_tokens)

    @classmethod
    def _is_adjustable(cls, category: object) -> bool:
        value = str(category or "").strip().lower()
        if value in {"food", "grocery", "groceries", "healthcare", "medical", "rent", "transport", "utilities"}:
            return False
        return bool(value) and any(token in value for token in cls._adjustable_tokens)

    def evaluate(self, user_id: str, request: GoalRequest) -> GoalEvaluation:
        transactions = self._dataset_service.get_user_transactions(user_id)
        if not transactions:
            return self._unavailable(user_id, request, "No transaction history is available for this account.")

        forecast = self._forecast_service.forecast(user_id)
        if not forecast.forecast_available:
            return self._unavailable(
                user_id,
                request,
                "At least six months of successful transaction history is required for Model 2.",
                history_months=forecast.history_months_available,
            )

        values = (forecast.expected_income, forecast.expected_committed_expenses,
                  forecast.expected_variable_expenses, forecast.expected_net_cash)
        if any(value is None or not isfinite(float(value)) for value in values):
            return self._unavailable(
                user_id, request,
                "The cash-flow forecast is unavailable, so this goal cannot be evaluated safely.",
                availability_status="forecast_unavailable",
            )

        required = float(ceil(float(request.goal_amount) / request.timeframe_months))
        expected_net = float(forecast.expected_net_cash)
        expected_variable = float(forecast.expected_variable_expenses)
        shortfall = max(required - expected_net, 0.0)
        adjustments = self._category_adjustments(transactions, forecast.variable_category_forecast, shortfall)
        total_adjustment = round(sum(item.suggested_reduction for item in adjustments), 2)
        adjusted_variable = max(expected_variable - total_adjustment, 0.0)
        expected_income = float(forecast.expected_income)
        committed = float(forecast.expected_committed_expenses)
        adjusted_net = round(expected_income - committed - adjusted_variable, 2)
        remaining = round(adjusted_net - required, 2)
        baseline_feasible = shortfall <= 0
        ml_feasible = self._predict_ml_feasibility(transactions, required)
        feasible = baseline_feasible
        remaining_gap = max(shortfall - total_adjustment, 0.0)

        if feasible:
            explanation = "The required monthly saving fits within the expected net cash remaining."
        elif remaining_gap <= 0:
            explanation = (
                f"The cash-flow gap can be covered by approximately "
                f"₹{total_adjustment:,.2f} per month is redirected from historically "
                "flexible, Model 1 category-forecast spending."
            )
        else:
            explanation = (
                f"Supported category adjustments cover ₹{total_adjustment:,.2f} of the "
                f"₹{shortfall:,.2f} monthly gap. ₹{remaining_gap:,.2f} remains; extend "
                "the timeframe, lower the target, increase income, or revise the savings plan."
            )

        return GoalEvaluation(
            user_id=user_id,
            goal_amount=round(request.goal_amount, 2),
            goal_months=request.timeframe_months,
            required_monthly_saving=self._money(required),
            expected_monthly_saving=self._money(expected_net),
            additional_monthly_saving_required=self._money(shortfall),
            goal_feasible=feasible,
            variable_spending_adjustment_required=self._money(shortfall),
            suggested_category_adjustments=adjustments,
            projected_variable_expenses_after_adjustment=self._money(adjusted_variable),
            projected_monthly_saving_after_adjustment=self._money(adjusted_net),
            remaining_money_after_goal_saving=self._money(remaining),
            explanation=explanation,
            availability_status="available",
            evaluation_metadata={
                "decision_method": (
                    "observed-future-behaviour-model"
                    if ml_feasible is not None
                    else "observed-history-flexibility-baseline"
                ),
                "model_1_version": forecast.model_version,
                "ml_status": "accepted" if ml_feasible is not None else "not_accepted",
                "ml_behavioural_signal": ml_feasible,
                "feasibility_status_source": "deterministic-model-1-net-cash-coverage",
                "category_recommendation_method": "deterministic-model-1-category-forecast-with-observed-history-floor",
                "remaining_savings_gap_after_recommendations": self._money(remaining_gap),
                "probability_exposed": False,
                "data_cutoff": forecast.data_cutoff,
            },
            model_version=(
                "model-2-phase-c-v2"
                if ml_feasible is not None
                else "model-2-baseline-v1"
            ),
        )

    def _predict_ml_feasibility(
        self,
        transactions: list[dict[str, Any]],
        required: float,
    ) -> bool | None:
        if self._model is None:
            return None
        frame = pd.DataFrame(transactions)
        if frame.empty:
            return None
        frame["amount"] = pd.to_numeric(frame.get("amount"), errors="coerce").fillna(0.0)
        frame["transaction_date"] = pd.to_datetime(frame.get("transaction_date"), errors="coerce")
        frame = frame.dropna(subset=["transaction_date"])
        frame["month"] = frame["transaction_date"].dt.to_period("M")
        statuses = frame.get("transaction_status", pd.Series("", index=frame.index))
        successful = statuses.fillna("").map(classify_transaction_status).eq(TransactionStatus.SUCCESSFUL)
        income = frame.get("income_flag", pd.Series(False, index=frame.index)).fillna(False).astype(str).str.lower().isin(
            {"yes", "true", "1"}
        )
        classes = frame.get("transaction_class", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
        positive = frame["amount"].clip(lower=0.0)
        monthly = pd.DataFrame(
            {
                "income": positive.where(successful & income, 0.0),
                "committed": positive.where(successful & ~income & classes.isin({"subscription", "emi", "bnpl"}), 0.0),
                "variable": positive.where(successful & ~income & ~classes.isin({"subscription", "emi", "bnpl"}), 0.0),
            },
            index=frame["month"],
        ).groupby(level=0).sum().sort_index()
        if len(monthly) < 6:
            return None
        history = monthly.tail(6)
        spending = history["committed"] + history["variable"]
        values = {
            "history_income_mean": float(history["income"].mean()),
            "history_income_std": float(history["income"].std(ddof=0)),
            "history_committed_mean": float(history["committed"].mean()),
            "history_variable_mean": float(history["variable"].mean()),
            "history_buffer_mean": float((history["income"] - spending).mean()),
            "history_buffer_min": float((history["income"] - spending).min()),
            "history_buffer_std": float((history["income"] - spending).std(ddof=0)),
            "history_income_trend": self._slope(history["income"].tolist()),
            "history_spending_trend": self._slope(spending.tolist()),
            "history_success_rate": float(successful.sum()) / max(float(len(frame)), 1.0),
            "required_monthly_saving": float(required),
        }
        features = pd.DataFrame([[values[column] for column in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
        try:
            return bool(self._model.predict(features)[0])
        except (AttributeError, KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _slope(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        x = list(range(len(values)))
        x_mean = sum(x) / len(x)
        y_mean = sum(values) / len(values)
        denominator = sum((value - x_mean) ** 2 for value in x)
        return sum((value - y_mean) * (index - x_mean) for index, value in enumerate(values)) / denominator if denominator else 0.0

    def create(self, user_id: str, request: GoalCreateRequest) -> FinancialGoalResponse:
        evaluation = self.evaluate(user_id, request)
        now = datetime.now(timezone.utc)
        with SessionLocal() as session:
            record = FinancialGoal(
                user_id=user_id,
                goal_name=request.goal_name,
                goal_amount=request.goal_amount,
                timeframe_months=request.timeframe_months,
                evaluation=evaluation.model_dump(mode="json"),
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return self._response(record)

    def list_for_user(self, user_id: str) -> list[FinancialGoalResponse]:
        with SessionLocal() as session:
            records = (
                session.query(FinancialGoal)
                .filter(FinancialGoal.user_id == user_id, FinancialGoal.is_active.is_(True))
                .order_by(FinancialGoal.created_at.desc())
                .all()
            )
            return [self._response(record) for record in records]

    def get_for_user(self, user_id: str, goal_id: int) -> FinancialGoalResponse:
        with SessionLocal() as session:
            record = (
                session.query(FinancialGoal)
                .filter(FinancialGoal.id == goal_id, FinancialGoal.user_id == user_id)
                .one_or_none()
            )
            if record is None:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Financial goal not found")
            return self._response(record)

    def update(self, user_id: str, goal_id: int, request: GoalUpdateRequest) -> FinancialGoalResponse:
        with SessionLocal() as session:
            record = (
                session.query(FinancialGoal)
                .filter(FinancialGoal.id == goal_id, FinancialGoal.user_id == user_id)
                .one_or_none()
            )
            if record is None:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Financial goal not found")
            goal_request = GoalRequest(
                goal_amount=request.goal_amount if request.goal_amount is not None else record.goal_amount,
                timeframe_months=(
                    request.timeframe_months
                    if request.timeframe_months is not None
                    else record.timeframe_months
                ),
            )
            evaluation = self.evaluate(user_id, goal_request)
            planned = (
                request.planned_monthly_contribution
                if request.planned_monthly_contribution is not None
                else record.planned_monthly_contribution
            )
            if planned is not None:
                capacity = evaluation.expected_monthly_saving
                if capacity is None:
                    from fastapi import HTTPException

                    raise HTTPException(status_code=422, detail="A monthly savings plan requires an available cash-flow forecast.")
                if planned > max(capacity, 0.0):
                    from fastapi import HTTPException

                    raise HTTPException(status_code=422, detail="Planned monthly contribution cannot exceed available net-cash capacity.")
            record.goal_amount = goal_request.goal_amount
            if request.goal_name is not None:
                record.goal_name = request.goal_name
            record.timeframe_months = goal_request.timeframe_months
            record.planned_monthly_contribution = planned
            record.evaluation = evaluation.model_dump(mode="json")
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return self._response(record)

    def deactivate(self, user_id: str, goal_id: int) -> FinancialGoalResponse:
        with SessionLocal() as session:
            record = (
                session.query(FinancialGoal)
                .filter(FinancialGoal.id == goal_id, FinancialGoal.user_id == user_id)
                .one_or_none()
            )
            if record is None:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Financial goal not found")
            record.is_active = False
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return self._response(record)

    @classmethod
    def _category_adjustments(
        cls,
        transactions: list[dict[str, Any]],
        forecast: dict[str, float],
        required: float,
    ) -> list[CategoryAdjustment]:
        frame = pd.DataFrame(transactions)
        if frame.empty or required <= 0:
            return []
        frame["amount"] = pd.to_numeric(frame.get("amount"), errors="coerce").fillna(0.0)
        frame["month"] = pd.to_datetime(frame.get("transaction_date"), errors="coerce").dt.to_period("M")
        status = frame.get("transaction_status", pd.Series("", index=frame.index))
        successful = status.map(classify_transaction_status).eq(TransactionStatus.SUCCESSFUL)
        income = frame.get("income_flag", pd.Series(False, index=frame.index)).fillna(False).astype(str).str.lower().isin(
            {"yes", "true", "1"}
        )
        classes = frame.get("transaction_class", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
        eligible = successful & frame["amount"].gt(0) & ~income & ~classes.isin({"subscription", "emi", "bnpl"})
        frame = frame.loc[eligible].copy()
        if frame.empty:
            return []

        candidates: list[CategoryAdjustment] = []
        for category, expected in forecast.items():
            categories = frame["category"] if "category" in frame.columns else pd.Series("", index=frame.index)
            category_rows = frame.loc[categories.fillna("").astype(str) == str(category)]
            if category_rows.empty or cls._is_protected(category) or not cls._is_adjustable(category):
                continue
            monthly = category_rows.groupby("month")["amount"].sum()
            if monthly.empty:
                continue
            if float(expected) > float(monthly.quantile(0.25)):
                flexible = max(float(expected) - float(monthly.quantile(0.25)), 0.0)
            else:
                flexible = round(float(expected) * cls.DISCRETIONARY_POLICY_TRIMMING_LIMIT, 2)
            candidates.append(
                CategoryAdjustment(
                    category=str(category),
                    current_expected_spending=round(float(expected), 2),
                    observed_monthly_spending=round(float(monthly.mean()), 2),
                    spending_basis="model_1_variable_category_forecast",
                    maximum_supported_reduction=round(min(flexible, float(expected)), 2),
                    suggested_reduction=round(min(flexible, float(expected)), 2),
                    adjusted_spending=round(max(float(expected) - flexible, 0.0), 2),
                    reduction_percent=round((flexible / expected * 100.0) if expected else 0.0, 2),
                    remaining_category_spending=round(max(float(expected) - flexible, 0.0), 2),
                    remaining_goal_savings_gap=round(required, 2),
                    evidence=(
                        "Model 1 category forecast is based on recent successful variable transactions; "
                        "the reduction is capped at the observed lower-quarter monthly spend."
                        if float(expected) > float(monthly.quantile(0.25))
                        else (
                            f"Model 1 forecast allocates ₹{round(float(expected), 2):,.2f}/mo. Discretionary policy limit "
                            f"caps trimming at {int(cls.DISCRETIONARY_POLICY_TRIMMING_LIMIT * 100)}% (₹{flexible:,.2f}/mo) "
                            f"to preserve a ₹{round(float(expected) - flexible, 2):,.2f}/mo essential baseline."
                        )
                    ),
                    protected=False,
                )
            )

        selected: list[CategoryAdjustment] = []
        remaining = required
        for item in sorted(candidates, key=lambda value: value.suggested_reduction, reverse=True):
            reduction = min(item.suggested_reduction, remaining)
            selected.append(item.model_copy(update={
                "suggested_reduction": round(reduction, 2),
                "adjusted_spending": round(item.current_expected_spending - reduction, 2),
                "reduction_percent": round(
                    reduction / item.current_expected_spending * 100.0
                    if item.current_expected_spending
                    else 0.0,
                    2,
                ),
                "remaining_category_spending": round(item.current_expected_spending - reduction, 2),
                "remaining_goal_savings_gap": max(round(remaining - reduction, 2), 0.0),
            }))
            remaining = round(remaining - reduction, 2)
            if remaining <= 0:
                break
        return selected

    @staticmethod
    def _unavailable(
        user_id: str,
        request: GoalRequest,
        explanation: str,
        history_months: int | None = None,
        availability_status: str = "insufficient_history",
    ) -> GoalEvaluation:
        return GoalEvaluation(
            user_id=user_id,
            goal_amount=round(request.goal_amount, 2),
            goal_months=request.timeframe_months,
            explanation=explanation,
            availability_status=availability_status,
            evaluation_metadata={
                "history_months_available": history_months,
                "ml_status": "not_accepted",
                "probability_exposed": False,
            },
        )

    @staticmethod
    def _response(record: FinancialGoal) -> FinancialGoalResponse:
        evaluation = dict(record.evaluation)
        planned = record.planned_monthly_contribution
        if planned is not None:
            capacity = evaluation.get("expected_monthly_saving")
            required = evaluation.get("required_monthly_saving")
            if isinstance(capacity, (int, float)) and isinstance(required, (int, float)):
                evaluation["planned_monthly_contribution"] = round(float(planned), 2)
                evaluation["money_remaining_after_planned_contribution"] = round(float(capacity) - float(planned), 2)
                plan_gap = round(max(float(required) - float(planned), 0.0), 2)
                evaluation["remaining_goal_savings_gap_after_plan"] = plan_gap
                if float(planned) >= float(required):
                    evaluation["goal_feasible"] = True
                    evaluation["explanation"] = (
                        f"Your saved monthly savings plan of ₹{float(planned):,.2f} fully covers "
                        f"the required monthly saving of ₹{float(required):,.2f}."
                    )
                elif float(planned) > 0:
                    evaluation["explanation"] = (
                        f"Your saved monthly contribution of ₹{float(planned):,.2f} is active. "
                        f"A remaining gap of ₹{plan_gap:,.2f}/mo can be covered by discretionary trimming or timeline adjustment."
                    )
        return FinancialGoalResponse(
            id=record.id,
            goal_name=record.goal_name or "Savings Goal",
            is_active=record.is_active,
            created_at=record.created_at,
            updated_at=record.updated_at,
            **evaluation,
        )


@lru_cache(maxsize=1)
def get_goal_feasibility_service() -> GoalFeasibilityService:
    dataset_service = get_dataset_service()
    return GoalFeasibilityService(dataset_service, get_cashflow_forecast_service())
