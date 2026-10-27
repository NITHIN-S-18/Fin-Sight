from __future__ import annotations

import hashlib
import pickle
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import Depends
from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models.financial_goal import FinancialGoal
from app.database.models.recurring_payment import RecurringPayment
from app.schemas.recurring_payment import (
    BatchCancellationSimulationRequest,
    BatchCancellationSimulationResponse,
    CancellationSimulationRequest,
    CancellationSimulationResponse,
    GoalImpactDetail,
    SelectedSubscriptionDetail,
    UserRecurringPaymentCreate,
    UserRecurringPaymentUpdate,
    RecurringPaymentListResponse,
    RecurringPaymentResponse,
)
from app.ml.subscription_usage import features_for_subscription
from app.services.cashflow_forecast_service import CashFlowForecastService, get_cashflow_forecast_service
from app.services.commitment_service import UnifiedCommitmentService
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.financial_rules import classify_transaction_status, commitment_amount, monthly_multiplier


@dataclass(frozen=True)
class _Frequency:
    label: str
    nominal_days: int


class RecurringPaymentService:
    _frequencies = (
        _Frequency("weekly", 7),
        _Frequency("biweekly", 14),
        _Frequency("monthly", 30),
        _Frequency("quarterly", 91),
        _Frequency("annual", 365),
    )
    _category_keywords = {
        "rent": ("rent", "landlord", "housing"),
        "insurance": ("insurance", "lic ", "lic-", "premium"),
        "electricity": ("electricity", "power", "bescom", "tneb", "msedcl"),
        "water": ("water", "municipal", "jal board"),
        "internet": ("broadband", "internet", "fiber", "fibre", "wifi"),
        "mobile": ("airtel", "jio", "vodafone", "vi ", "recharge", "mobile"),
        "education": ("school", "college", "tuition", "coaching", "education"),
        "investment": ("sip", "mutual fund", "investment", "zerodha", "groww"),
        "membership": ("gym", "club", "membership", "cult.fit"),
    }
    _class_categories = {
        "subscription": "subscription",
        "emi": "emi",
        "loan": "emi",
        "bnpl": "bnpl",
    }
    _variable_categories = {"electricity", "water", "internet", "mobile"}

    def __init__(
        self,
        dataset_service: DatasetService,
        forecast_service: CashFlowForecastService | None = None,
    ) -> None:
        self._dataset_service = dataset_service
        self._forecast_service = forecast_service
        self._usage_model = self._load_usage_model()

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_usage_model() -> Any | None:
        path = (
            Path(__file__).resolve().parents[1]
            / "ml"
            / "saved_models"
            / "financial_subscription_usage"
            / "v1.0"
            / "artifact.pkl"
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
    def _text(value: Any) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        return str(value).strip()

    @classmethod
    def _normalized_text(cls, value: Any) -> str:
        text = cls._text(value).lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _group_key(cls, row: dict[str, Any]) -> str:
        merchant = cls._normalized_text(row.get("merchant_name"))
        if merchant:
            return merchant
        description = cls._normalized_text(row.get("description"))
        description = re.sub(r"\b\d+\b", "", description)
        return re.sub(r"\s+", " ", description).strip()

    @classmethod
    def _category(cls, row: dict[str, Any]) -> str:
        transaction_class = cls._normalized_text(row.get("transaction_class"))
        if transaction_class in cls._class_categories:
            return cls._class_categories[transaction_class]
        source = " ".join(
            part for part in (row.get("merchant_name"), row.get("description"), row.get("category")) if part
        ).lower()
        for category, keywords in cls._category_keywords.items():
            if any(keyword in source for keyword in keywords):
                return category
        category = cls._normalized_text(row.get("category"))
        return category if category else "other"

    @classmethod
    def _frequency(cls, dates: list[date], explicit: list[str]) -> _Frequency | None:
        if len(dates) < 2:
            return None
        intervals = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
        if any(interval <= 0 for interval in intervals):
            return None
        median_interval = float(pd.Series(intervals).median())
        candidates = sorted(
            cls._frequencies,
            key=lambda item: abs(item.nominal_days - median_interval),
        )
        selected = candidates[0]
        if abs(selected.nominal_days - median_interval) > 5:
            normalized_explicit = {cls._normalized_text(value) for value in explicit}
            explicit_match = next(
                (item for item in cls._frequencies if item.label in normalized_explicit),
                None,
            )
            if explicit_match is None:
                return None
            selected = explicit_match
        if any(abs(interval - selected.nominal_days) > 5 for interval in intervals):
            return None
        return selected

    @classmethod
    def _amount_consistent(cls, amounts: list[float], category: str) -> bool:
        if not amounts:
            return False
        average = sum(amounts) / len(amounts)
        if average <= 0:
            return False
        tolerance = 0.5 if category in cls._variable_categories else 0.1
        return (max(amounts) - min(amounts)) / average <= tolerance

    @classmethod
    def _candidate_groups(cls, transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for transaction in transactions:
            if classify_transaction_status(transaction.get("transaction_status")).value != "successful":
                continue
            income_flag = str(transaction.get("income_flag", "")).strip().lower()
            if income_flag in {"yes", "true", "1", "y"}:
                continue
            if cls._normalized_text(transaction.get("transaction_class")) in {
                "income",
                "salary",
                "credit",
                "refund",
            }:
                continue
            if cls._normalized_text(transaction.get("category")) in {
                "income",
                "salary",
            }:
                continue
            if cls._normalized_text(transaction.get("merchant_type")) in {"employer"}:
                continue
            if cls._normalized_text(transaction.get("transaction_type")) in {"credit", "cr"}:
                continue
            amount = commitment_amount(transaction.get("amount"))
            if amount <= 0:
                continue
            key = cls._group_key(transaction)
            if not key:
                continue
            category = cls._category(transaction)
            groups.setdefault((key, category), []).append(transaction)

        candidates: list[dict[str, Any]] = []
        for (key, category), rows in groups.items():
            ordered = sorted(
                rows,
                key=lambda row: pd.Timestamp(row["transaction_date"]).date(),
            )
            dates = [pd.Timestamp(row["transaction_date"]).date() for row in ordered]
            frequency = cls._frequency(
                dates,
                [cls._text(row.get("frequency")) for row in ordered],
            )
            if frequency is None or len(ordered) < 2:
                continue
            amounts = [commitment_amount(row.get("amount")) for row in ordered]
            if not cls._amount_consistent(amounts, category):
                continue
            high_confidence = len(ordered) >= 3
            confidence_level = "high" if high_confidence else "low"
            confidence = 0.9 if high_confidence else 0.55
            typical_amount = round(sum(amounts) / len(amounts), 2)
            last_date = dates[-1]
            candidates.append(
                {
                    "detection_key": f"{category}:{key}",
                    "name": cls._text(ordered[-1].get("merchant_name")) or key.title(),
                    "category": category,
                    "amount": typical_amount,
                    "frequency": frequency.label,
                    "monthly_equivalent_amount": round(
                        typical_amount * monthly_multiplier(frequency.label), 2
                    ),
                    "last_payment_date": last_date,
                    "next_expected_date": last_date + timedelta(days=frequency.nominal_days),
                    "status": "Active",
                    "confidence": confidence,
                    "confidence_level": confidence_level,
                    "source": "DETECTED",
                    "is_active": True,
                    "supporting_transaction_ids": [
                        str(row["transaction_id"]) for row in ordered
                    ],
                    "evidence": {
                        "occurrence_count": len(ordered),
                        "interval_days": [
                            (later - earlier).days for earlier, later in zip(dates, dates[1:])
                        ],
                        "amount_range": [min(amounts), max(amounts)],
                        "low_confidence_review_required": not high_confidence,
                    },
                }
            )
        return candidates

    def reconcile(self, user_id: str) -> int:
        # Uploads invalidate the cached DatasetService after committing new rows.
        # Resolve it again so reconciliation always observes the committed ledger.
        transactions = get_dataset_service().get_user_transactions(user_id)
        candidates = self._candidate_groups(transactions)
        with SessionLocal() as session:
            existing = {
                row.detection_key: row
                for row in session.scalars(
                    select(RecurringPayment).where(
                        RecurringPayment.user_id == user_id,
                        RecurringPayment.source == "DETECTED",
                    )
                ).all()
            }
            seen_keys = set()
            for candidate in candidates:
                seen_keys.add(candidate["detection_key"])
                row = existing.get(candidate["detection_key"])
                if row is None:
                    row = RecurringPayment(user_id=user_id, **candidate)
                    session.add(row)
                else:
                    for field, value in candidate.items():
                        setattr(row, field, value)
            for key, row in list(existing.items()):
                if (
                    row.category.casefold() in {"income", "salary"}
                    or "salary" in row.name.casefold()
                    or "acme" in row.name.casefold()
                ):
                    session.delete(row)
                    existing.pop(key, None)
                elif key not in seen_keys:
                    row.status = "Inactive"
                    row.is_active = False
            session.commit()
        return len(candidates)

    @staticmethod
    def _user_added_key(user_id: str, data: UserRecurringPaymentCreate) -> str:
        identity = "|".join(
            [user_id, data.name.casefold(), data.category, f"{data.amount:.2f}",
             data.frequency, data.next_expected_date.isoformat()]
        )
        return "user:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _manual_monthly_amount(amount: float, frequency: str) -> float:
        return round(amount * monthly_multiplier(frequency), 2)

    def create_user_added(
        self, user_id: str, data: UserRecurringPaymentCreate
    ) -> RecurringPaymentResponse:
        if data.is_active and data.next_expected_date < date.today():
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An active recurring payment must have a current or future next payment date.",
            )
        detection_key = self._user_added_key(user_id, data)
        with SessionLocal() as session:
            duplicate = session.scalar(
                select(RecurringPayment).where(
                    RecurringPayment.user_id == user_id,
                    RecurringPayment.source == "USER_ADDED",
                    RecurringPayment.detection_key == detection_key,
                )
            )
            if duplicate is not None:
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An identical user-added recurring payment already exists.",
                )
            row = RecurringPayment(
                user_id=user_id,
                detection_key=detection_key,
                name=data.name,
                category=data.category,
                amount=data.amount,
                frequency=data.frequency,
                monthly_equivalent_amount=self._manual_monthly_amount(data.amount, data.frequency),
                last_payment_date=None,
                next_expected_date=data.next_expected_date,
                status="Active" if data.is_active else "Inactive",
                confidence=1.0,
                confidence_level="confirmed",
                source="USER_ADDED",
                is_active=data.is_active,
                supporting_transaction_ids=[],
                evidence={},
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return RecurringPaymentResponse.model_validate(row)

    def list_for_user(
        self,
        user_id: str,
        category: str | None = None,
        confidence_level: str | None = None,
        status: str | None = None,
    ) -> RecurringPaymentListResponse:
        with SessionLocal() as session:
            query = select(RecurringPayment).where(
                RecurringPayment.user_id == user_id,
                RecurringPayment.category.notin_(["income", "salary"]),
                ~RecurringPayment.name.ilike("%salary%"),
                ~RecurringPayment.name.ilike("%acme technologies%"),
            )
            if category:
                query = query.where(RecurringPayment.category.ilike(category))
            if confidence_level:
                query = query.where(RecurringPayment.confidence_level.ilike(confidence_level))
            if status:
                query = query.where(RecurringPayment.status.ilike(status))
            rows = session.scalars(
                query.order_by(RecurringPayment.monthly_equivalent_amount.desc(), RecurringPayment.name)
            ).all()
            transactions = self._dataset_service.get_user_transactions(user_id)
            items = [self._with_engagement(RecurringPaymentResponse.model_validate(row), row, transactions) for row in rows]
            return RecurringPaymentListResponse(items=items, total=len(items))

    def get_for_user(self, user_id: str, recurring_payment_id: int) -> RecurringPaymentResponse:
        with SessionLocal() as session:
            row = session.scalar(
                select(RecurringPayment).where(
                    RecurringPayment.id == recurring_payment_id,
                    RecurringPayment.user_id == user_id,
                )
            )
            if row is None:
                from fastapi import HTTPException, status

                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring payment not found")
            transactions = self._dataset_service.get_user_transactions(user_id)
            return self._with_engagement(RecurringPaymentResponse.model_validate(row), row, transactions)

    def _with_engagement(
        self,
        response: RecurringPaymentResponse,
        row: RecurringPayment,
        transactions: list[dict[str, Any]],
    ) -> RecurringPaymentResponse:
        if row.source != "DETECTED" or not row.is_active or self._usage_model is None:
            return response
        frame = pd.DataFrame(transactions)
        features = features_for_subscription(frame, row.name)
        if features.empty:
            return response
        try:
            prediction = str(self._usage_model.predict(features)[0])
        except (AttributeError, KeyError, TypeError, ValueError):
            return response
        explanation = {
            "ACTIVE": "Transactional engagement appears consistent based on successful recurring payment continuity.",
            "MODERATE": "Transactional engagement appears irregular based on payment continuity and recent gaps.",
            "UNDER_UTILIZED": "Transactional engagement appears low based on prolonged payment inactivity.",
        }.get(prediction, "Transactional engagement could not be determined from payment history.")
        return response.model_copy(
            update={
                "transactional_engagement_status": prediction,
                "transactional_engagement_explanation": explanation,
            }
        )

    def simulate_cancellation(
        self,
        user_id: str,
        recurring_payment_id: int,
        request: CancellationSimulationRequest,
    ) -> CancellationSimulationResponse:
        with SessionLocal() as session:
            row = session.scalar(
                select(RecurringPayment).where(
                    RecurringPayment.id == recurring_payment_id,
                    RecurringPayment.user_id == user_id,
                )
            )
            if row is None:
                from fastapi import HTTPException, status

                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring payment not found.")
            snapshot = UnifiedCommitmentService.snapshot_for_user(user_id, session)
            item = next((item for item in snapshot.commitment_items if item.id == row.id), None)
            monthly_item = round(float(item.monthly_equivalent_amount if item else 0.0), 2)

        forecast_service = self._forecast_service or get_cashflow_forecast_service()
        forecast = forecast_service.forecast(user_id)
        current_expenses = forecast.expected_total_expenses if forecast.forecast_available else None
        current_cash = forecast.expected_net_cash if forecast.forecast_available else None
        projected_expenses = round(current_expenses - monthly_item, 2) if current_expenses is not None else None
        projected_cash = round(current_cash + monthly_item, 2) if current_cash is not None else None
        required = (
            request.goal_amount / request.timeframe_months
            if request.goal_amount is not None and request.timeframe_months is not None
            else None
        )
        current_goal = round(current_cash, 2) >= required if current_cash is not None and required is not None else None
        projected_goal = round(projected_cash, 2) >= required if projected_cash is not None and required is not None else None
        return CancellationSimulationResponse(
            recurring_payment_id=row.id,
            subscription_name=row.name,
            current_monthly_subscription_commitment=round(
                snapshot.breakdown_by_category.get("subscription", 0.0), 2
            ),
            projected_monthly_subscription_commitment=round(
                max(snapshot.breakdown_by_category.get("subscription", 0.0) - (monthly_item if row.category == "subscription" else 0.0), 0.0),
                2,
            ),
            current_total_monthly_commitments=snapshot.total_monthly_commitments,
            projected_total_monthly_commitments=round(max(snapshot.total_monthly_commitments - monthly_item, 0.0), 2),
            current_monthly_expenses=current_expenses,
            projected_monthly_expenses=projected_expenses,
            current_available_cash=current_cash,
            projected_available_cash=projected_cash,
            additional_monthly_savings=monthly_item,
            annual_potential_savings=round(monthly_item * 12.0, 2),
            current_goal_feasible=current_goal,
            projected_goal_feasible=projected_goal,
            explanation=f"Simulation only: deactivating {row.name} would redirect approximately ₹{monthly_item:,.2f} per month. No record was changed.",
        )

    def simulate_batch_cancellation(
        self,
        user_id: str,
        request: BatchCancellationSimulationRequest,
    ) -> BatchCancellationSimulationResponse:
        with SessionLocal() as session:
            snapshot = UnifiedCommitmentService.snapshot_for_user(user_id, session)

            # Deduplicate requested IDs while preserving order
            requested_ids = list(dict.fromkeys(request.recurring_payment_ids))

            selected_subs: list[SelectedSubscriptionDetail] = []
            if requested_ids:
                rows = session.scalars(
                    select(RecurringPayment).where(
                        RecurringPayment.id.in_(requested_ids),
                        RecurringPayment.user_id == user_id,
                    )
                ).all()
                row_map = {row.id: row for row in rows}

                # Verify that all requested IDs belong to the user
                missing_ids = [rid for rid in requested_ids if rid not in row_map]
                if missing_ids:
                    from fastapi import HTTPException, status

                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Recurring payment ID(s) {missing_ids} not found for authenticated user.",
                    )

                transactions = self._dataset_service.get_user_transactions(user_id)
                for rid in requested_ids:
                    row = row_map[rid]
                    engagement = None
                    if row.source == "DETECTED" and row.is_active and self._usage_model is not None:
                        frame = pd.DataFrame(transactions)
                        feats = features_for_subscription(frame, row.name)
                        if not feats.empty:
                            try:
                                engagement = str(self._usage_model.predict(feats)[0])
                            except (AttributeError, KeyError, TypeError, ValueError):
                                pass

                    item = next((i for i in snapshot.commitment_items if i.id == row.id), None)
                    monthly_amt = round(
                        float(item.monthly_equivalent_amount if item else row.monthly_equivalent_amount), 2
                    )

                    selected_subs.append(
                        SelectedSubscriptionDetail(
                            id=row.id,
                            name=row.name,
                            category=row.category,
                            frequency=row.frequency,
                            original_amount=round(float(row.amount), 2),
                            monthly_equivalent_amount=monthly_amt,
                            engagement_status=engagement,
                        )
                    )

            monthly_savings = round(sum(s.monthly_equivalent_amount for s in selected_subs), 2)
            annual_savings = round(monthly_savings * 12.0, 2)
            current_total_commitments = snapshot.total_monthly_commitments
            projected_total_commitments = max(round(current_total_commitments - monthly_savings, 2), 0.0)

            current_sub_commitments = round(snapshot.breakdown_by_category.get("subscription", 0.0), 2)
            sub_category_savings = sum(
                s.monthly_equivalent_amount for s in selected_subs if s.category == "subscription"
            )
            projected_sub_commitments = max(round(current_sub_commitments - sub_category_savings, 2), 0.0)

            current_expenses = None
            current_cash = None
            try:
                forecast_service = self._forecast_service or get_cashflow_forecast_service()
                forecast = forecast_service.forecast(user_id)
                if forecast.forecast_available:
                    current_expenses = forecast.expected_total_expenses
                    current_cash = forecast.expected_net_cash
            except Exception:
                pass

            projected_expenses = (
                max(round(current_expenses - monthly_savings, 2), 0.0)
                if current_expenses is not None
                else None
            )
            projected_cash = (
                round(current_cash + monthly_savings, 2) if current_cash is not None else None
            )

            # Financial Goal Impact
            goal_impact: GoalImpactDetail | None = None
            goal = None
            if request.goal_id:
                goal = session.scalar(
                    select(FinancialGoal).where(
                        FinancialGoal.id == request.goal_id,
                        FinancialGoal.user_id == user_id,
                        FinancialGoal.is_active == True,
                    )
                )
            elif request.goal_amount is not None and request.timeframe_months is not None:
                required_saving = round(request.goal_amount / request.timeframe_months, 2)
                curr_gap = max(round(required_saving - (current_cash or 0.0), 2), 0.0) if current_cash is not None else 0.0
                proj_gap = max(round(required_saving - (projected_cash or 0.0), 2), 0.0) if projected_cash is not None else 0.0
                gap_closed = min(round((curr_gap - proj_gap) / curr_gap * 100.0, 1), 100.0) if curr_gap > 0 else 100.0
                curr_feas = (current_cash or 0.0) >= required_saving if current_cash is not None else None
                proj_feas = (projected_cash or 0.0) >= required_saving if projected_cash is not None else None

                goal_impact = GoalImpactDetail(
                    goal_id=None,
                    goal_name="Hypothetical Goal",
                    target_amount=request.goal_amount,
                    timeframe_months=request.timeframe_months,
                    required_monthly_saving=required_saving,
                    current_available_cash=current_cash,
                    projected_available_cash=projected_cash,
                    current_gap=curr_gap,
                    projected_gap=proj_gap,
                    gap_closed_percent=gap_closed,
                    current_goal_feasible=curr_feas,
                    projected_goal_feasible=proj_feas,
                    explanation=(
                        f"Saving ₹{monthly_savings:,.0f}/mo increases your expected net cash to ₹{projected_cash:,.0f}/mo, closing {gap_closed:.0f}% of the gap."
                        if curr_gap > 0
                        else f"Saving ₹{monthly_savings:,.0f}/mo expands your monthly surplus to ₹{(projected_cash or 0.0) - required_saving:,.0f}/mo."
                    ),
                )
            else:
                goal = session.scalar(
                    select(FinancialGoal).where(
                        FinancialGoal.user_id == user_id,
                        FinancialGoal.is_active == True,
                    ).order_by(FinancialGoal.created_at.desc())
                )

            if goal is not None and goal_impact is None:
                evaluation = dict(goal.evaluation) if goal.evaluation else {}
                req = evaluation.get("required_monthly_saving") or round(goal.goal_amount / goal.timeframe_months, 2)
                required_saving = float(req)
                curr_cash_val = current_cash if current_cash is not None else 0.0
                proj_cash_val = projected_cash if projected_cash is not None else 0.0
                curr_gap = max(round(required_saving - curr_cash_val, 2), 0.0)
                proj_gap = max(round(required_saving - proj_cash_val, 2), 0.0)
                gap_closed = min(round((curr_gap - proj_gap) / curr_gap * 100.0, 1), 100.0) if curr_gap > 0 else 100.0
                curr_feas = curr_cash_val >= required_saving
                proj_feas = proj_cash_val >= required_saving

                explanation_str = (
                    f"Saving ₹{monthly_savings:,.0f}/mo increases your expected net cash to ₹{proj_cash_val:,.0f}/mo, closing {gap_closed:.0f}% of the gap for your {goal.goal_name} goal."
                    if curr_gap > 0
                    else f"Saving ₹{monthly_savings:,.0f}/mo expands your monthly surplus for {goal.goal_name} to ₹{proj_cash_val - required_saving:,.0f}/mo."
                )
                goal_impact = GoalImpactDetail(
                    goal_id=goal.id,
                    goal_name=goal.goal_name,
                    target_amount=goal.goal_amount,
                    timeframe_months=goal.timeframe_months,
                    required_monthly_saving=required_saving,
                    current_available_cash=current_cash,
                    projected_available_cash=projected_cash,
                    current_gap=curr_gap,
                    projected_gap=proj_gap,
                    gap_closed_percent=gap_closed,
                    current_goal_feasible=curr_feas,
                    projected_goal_feasible=proj_feas,
                    explanation=explanation_str,
                )

            return BatchCancellationSimulationResponse(
                selected_count=len(selected_subs),
                selected_subscriptions=selected_subs,
                current_total_monthly_commitments=current_total_commitments,
                projected_total_monthly_commitments=projected_total_commitments,
                current_monthly_subscription_commitment=current_sub_commitments,
                projected_monthly_subscription_commitment=projected_sub_commitments,
                monthly_savings=monthly_savings,
                annual_potential_savings=annual_savings,
                current_available_cash=current_cash,
                projected_available_cash=projected_cash,
                goal_impact=goal_impact,
                cancellation_applied=False,
                explanation=(
                    f"Simulation only: cancelling {len(selected_subs)} selected subscription(s) would redirect "
                    f"approximately ₹{monthly_savings:,.2f} per month (+₹{annual_savings:,.2f}/year). No stored commitments were changed."
                ),
            )

    def update_user_added(
        self, user_id: str, recurring_payment_id: int, data: UserRecurringPaymentUpdate
    ) -> RecurringPaymentResponse:
        with SessionLocal() as session:
            row = session.scalar(
                select(RecurringPayment).where(
                    RecurringPayment.id == recurring_payment_id,
                    RecurringPayment.user_id == user_id,
                )
            )
            self._require_user_added(row)
            changes = data.model_dump(exclude_unset=True)
            if not changes:
                return RecurringPaymentResponse.model_validate(row)
            if any(
                field in changes and changes[field] is None
                for field in ("name", "category", "amount", "frequency", "next_expected_date", "is_active")
            ):
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Updated recurring-payment fields must not be null.",
                )
            for field, value in changes.items():
                setattr(row, field, value)
            if row.is_active and row.next_expected_date < date.today():
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="An active recurring payment must have a current or future next payment date.",
                )
            identity = UserRecurringPaymentCreate(
                name=row.name,
                category=row.category,
                amount=row.amount,
                frequency=row.frequency,
                next_expected_date=row.next_expected_date,
                is_active=row.is_active,
            )
            new_key = self._user_added_key(user_id, identity)
            duplicate = session.scalar(
                select(RecurringPayment).where(
                    RecurringPayment.user_id == user_id,
                    RecurringPayment.source == "USER_ADDED",
                    RecurringPayment.detection_key == new_key,
                    RecurringPayment.id != recurring_payment_id,
                )
            )
            if duplicate is not None:
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An identical user-added recurring payment already exists.",
                )
            row.detection_key = new_key
            row.status = "Active" if row.is_active else "Inactive"
            row.monthly_equivalent_amount = self._manual_monthly_amount(row.amount, row.frequency)
            session.commit()
            session.refresh(row)
            return RecurringPaymentResponse.model_validate(row)

    def deactivate_user_added(self, user_id: str, recurring_payment_id: int) -> RecurringPaymentResponse:
        with SessionLocal() as session:
            row = session.scalar(
                select(RecurringPayment).where(
                    RecurringPayment.id == recurring_payment_id,
                    RecurringPayment.user_id == user_id,
                )
            )
            self._require_user_added(row)
            row.is_active = False
            row.status = "Inactive"
            session.commit()
            session.refresh(row)
            return RecurringPaymentResponse.model_validate(row)

    @staticmethod
    def _require_user_added(row: RecurringPayment | None) -> RecurringPayment:
        from fastapi import HTTPException, status

        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring payment not found.")
        if row.source != "USER_ADDED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Detected recurring payments cannot be edited or deactivated.",
            )
        return row


@lru_cache(maxsize=1)
def get_recurring_payment_service() -> RecurringPaymentService:
    return RecurringPaymentService(
        get_dataset_service(),
        get_cashflow_forecast_service(),
    )
