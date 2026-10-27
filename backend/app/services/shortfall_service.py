from __future__ import annotations

import pandas as pd
from functools import lru_cache

from app.core.exceptions import ExposureDataUnavailableError
from app.ml.persistence import ModelPersistenceManager
from app.ml.shortfall import current_features, monthly_cashflow
from app.schemas.ml import FinancialShortfallResponse, ShortfallFactorDetail
from app.services.cashflow_forecast_service import CashFlowForecastService
from app.services.commitment_service import UnifiedCommitmentService
from app.services.dataset_service import DatasetService, get_dataset_service


class FinancialShortfallService:
    def __init__(
        self,
        dataset_service: DatasetService | None = None,
        forecast_service: CashFlowForecastService | None = None,
        persistence: ModelPersistenceManager | None = None,
    ) -> None:
        self._dataset_service = dataset_service or get_dataset_service()
        self._forecast_service = forecast_service or CashFlowForecastService(self._dataset_service)
        self._persistence = persistence or ModelPersistenceManager()

    def predict(self, user_id: str) -> FinancialShortfallResponse:
        transactions = self._dataset_service.get_user_transactions(user_id)
        frame = pd.DataFrame(transactions)
        monthly = monthly_cashflow(frame)
        if monthly.empty or len(monthly) < 6:
            horizon = str(monthly.index.max() + 1) if not monthly.empty else "unavailable"
            return FinancialShortfallResponse(
                user_id=user_id,
                available=False,
                model_version="unavailable",
                prediction="UNAVAILABLE",
                shortfall_risk="UNAVAILABLE",
                next_month_horizon=horizon,
                availability_status="insufficient_history",
            )
        try:
            forecast = self._forecast_service.forecast(user_id)
        except ExposureDataUnavailableError:
            forecast = None
        features, horizon = current_features(frame, forecast)
        if features is None or horizon is None:
            return FinancialShortfallResponse(
                user_id=user_id,
                available=False,
                model_version="unavailable",
                prediction="UNAVAILABLE",
                shortfall_risk="UNAVAILABLE",
                next_month_horizon="unavailable",
                availability_status="insufficient_history",
            )
        self._apply_authoritative_commitments(features, user_id)
        try:
            bundle = self._persistence.load("financial_shortfall", "v1.0")
        except (FileNotFoundError, TypeError, ValueError):
            return self._baseline_response(user_id, horizon, forecast, features)
        pipeline = self._pipeline(bundle)
        transformed = pipeline.transform(features)
        score = float(bundle.model.predict_proba(transformed)[:, 1][0])
        threshold = float(bundle.artifact.metadata.get("threshold", 0.5))
        exp_net = getattr(forecast, "expected_net_cash", None) if forecast else None
        net_cash_6m = float(features.iloc[0].get("net_cash_6m", 0.0))
        min_net_cash = float(features.iloc[0].get("minimum_net_cash", 0.0))
        has_actual_deficit = (exp_net is not None and exp_net < 0) or (net_cash_6m < 0)

        likely = bool(score >= threshold)
        if likely and not has_actual_deficit and exp_net is not None and exp_net > 0 and min_net_cash >= 0:
            # Positive forecast surplus and no historical negative cash flow months:
            # Model score elevation reflects spending variance or commitment tightening, not outright deficit.
            likely = False
            risk = "MODERATE"
        elif likely and score >= 0.75:
            risk = "HIGH"
        elif likely or score >= 0.35:
            risk = "MODERATE"
        else:
            risk = "LOW"
        factors, actions, factor_details, explanation = self._explain(features.iloc[0], forecast, likely, risk)
        return FinancialShortfallResponse(
            user_id=user_id,
            available=True,
            model_version=bundle.artifact.model_version,
            prediction="LIKELY_SHORTFALL" if likely else "UNLIKELY_SHORTFALL",
            shortfall_risk=risk,
            next_month_horizon=horizon,
            expected_net_cash=getattr(forecast, "expected_net_cash", None),
            expected_income=getattr(forecast, "expected_income", None),
            expected_total_expenses=getattr(forecast, "expected_total_expenses", None),
            contributing_factors=factors,
            factor_details=factor_details,
            risk_explanation=explanation,
            recommended_actions=actions,
            availability_status="available",
        )

    @staticmethod
    def _apply_authoritative_commitments(features: pd.DataFrame, user_id: str) -> None:
        snapshot = UnifiedCommitmentService.snapshot_for_user(user_id)
        row = features.iloc[0]
        from app.services.income_service import IncomeService
        income_service = IncomeService()
        effective_income, _, _, _, _ = income_service.resolve_effective_income(user_id, float(row["income_6m"]))
        income = max(float(effective_income), 1.0)
        total = float(snapshot.total_monthly_commitments)
        breakdown = snapshot.breakdown_by_category
        features.loc[0, "total_monthly_commitments"] = total
        features.loc[0, "active_recurring_count"] = float(snapshot.active_commitment_count)
        features.loc[0, "commitment_burden"] = total / income
        features.loc[0, "commitment_ratio"] = total / income
        features.loc[0, "subscription_burden"] = float(breakdown.get("subscription", 0.0))
        features.loc[0, "emi_burden"] = float(breakdown.get("emi", 0.0))
        features.loc[0, "bnpl_burden"] = float(breakdown.get("bnpl", 0.0))
        features.loc[0, "recurring_payment_burden"] = (
            features.loc[0, "subscription_burden"]
            + features.loc[0, "emi_burden"]
            + features.loc[0, "bnpl_burden"]
        )

    @staticmethod
    def _pipeline(bundle):
        from app.ml.preprocessing import PreprocessingPipeline

        if bundle.preprocessor_state is None:
            raise ValueError("Shortfall artifact has no preprocessing state.")
        return PreprocessingPipeline.from_state(bundle.preprocessor_state)

    def _baseline_response(self, user_id, horizon, forecast, features):
        net_cash_6m = float(features.iloc[0]["net_cash_6m"])
        volatility = float(features.iloc[0]["net_cash_volatility"])
        buffer = net_cash_6m - volatility
        exp_net = getattr(forecast, "expected_net_cash", None) if forecast else None

        if net_cash_6m < 0 or (exp_net is not None and exp_net < 0):
            likely = True
            risk = "HIGH"
        elif buffer < 0:
            likely = False
            risk = "MODERATE"
        else:
            likely = False
            risk = "LOW"
        factors, actions, factor_details, explanation = self._explain(features.iloc[0], forecast, likely, risk)
        return FinancialShortfallResponse(
            user_id=user_id,
            available=True,
            model_version="baseline-v1",
            prediction="LIKELY_SHORTFALL" if likely else "UNLIKELY_SHORTFALL",
            shortfall_risk=risk,
            next_month_horizon=horizon,
            expected_net_cash=getattr(forecast, "expected_net_cash", None),
            expected_income=getattr(forecast, "expected_income", None),
            expected_total_expenses=getattr(forecast, "expected_total_expenses", None),
            contributing_factors=factors,
            factor_details=factor_details,
            risk_explanation=explanation,
            recommended_actions=actions,
            availability_status="available",
        )

    @staticmethod
    def _explain(row, forecast, likely, shortfall_risk="LOW"):
        factors: list[str] = []
        actions: list[str] = []
        factor_details: list[ShortfallFactorDetail] = []

        def _get(key: str, default: float = 0.0) -> float:
            try:
                val = row[key] if hasattr(row, "__getitem__") else getattr(row, key, default)
                return float(val) if val is not None and not pd.isna(val) else default
            except (KeyError, IndexError, TypeError):
                return default

        income_6m = max(_get("income_6m", 1.0), 1.0)
        income_trend = _get("income_trend", 0.0)
        income_stability = _get("income_stability", 0.0)
        variable_trend = _get("variable_trend", 0.0)
        commitment_growth = _get("commitment_growth", 0.0)
        commitment_ratio = _get("commitment_ratio", 0.0)
        variable_volatility = _get("variable_volatility", 0.0)
        variable_6m = _get("variable_6m", 0.0)
        net_cash_6m = _get("net_cash_6m", 0.0)
        minimum_net_cash = _get("minimum_net_cash", 0.0)
        net_cash_volatility = _get("net_cash_volatility", 0.0)
        buffer = net_cash_6m - net_cash_volatility

        # 1. Income Trend Factor
        # Machine-epsilon guard: flat income has near-zero slope or 1.0 stability.
        # Genuine decline requires at least 1% drop per month and at least ₹50/mo.
        if income_trend <= -max(income_6m * 0.01, 50.0) and income_stability < 0.99:
            severity = "HIGH" if income_trend < -max(income_6m * 0.05, 1000.0) else "MEDIUM"
            f_name = "declining historical income trend"
            factors.append(f_name)
            factor_details.append(
                ShortfallFactorDetail(
                    factor=f_name,
                    severity=severity,
                    description="Average monthly income has trended downward across recent months.",
                )
            )

        # 2. Expense Increase Factor
        # Validate against meaningful upward trend (> 2% of income or > ₹500/mo).
        if variable_trend >= max(income_6m * 0.02, 50.0) or commitment_growth >= max(income_6m * 0.05, 50.0):
            f_name = "recent expense increase"
            factors.append(f_name)
            actions.append("review non-essential spending")
            factor_details.append(
                ShortfallFactorDetail(
                    factor=f_name,
                    severity="MEDIUM",
                    description="Monthly variable or commitment spending trended upward in recent months.",
                )
            )
        elif variable_volatility > max(variable_6m * 0.5, 5000.0):
            f_name = "high variable-spending volatility"
            factors.append(f_name)
            actions.append("reduce discretionary spending")
            factor_details.append(
                ShortfallFactorDetail(
                    factor=f_name,
                    severity="MEDIUM",
                    description="Discretionary and variable outflows fluctuate significantly month-to-month.",
                )
            )

        # 3. Recurring Commitment Burden Factor
        if commitment_ratio > 0.6:
            f_name = "high recurring commitment burden"
            factors.append(f_name)
            actions.append("review upcoming recurring commitments")
            factor_details.append(
                ShortfallFactorDetail(
                    factor=f_name,
                    severity="HIGH",
                    description="A high share of monthly income is committed to recurring contractual obligations.",
                )
            )

        # 4. Cash Buffer Factor
        if net_cash_6m < 0 or buffer < 0:
            f_name = "low historical cash buffer"
            factors.append(f_name)
            actions.append("increase cash buffer")
            factor_details.append(
                ShortfallFactorDetail(
                    factor=f_name,
                    severity="HIGH",
                    description="Historical monthly net cash balance is low or negative relative to spending.",
                )
            )
        elif minimum_net_cash < 0:
            f_name = "low historical cash buffer"
            factors.append(f_name)
            actions.append("increase cash buffer")
            factor_details.append(
                ShortfallFactorDetail(
                    factor=f_name,
                    severity="MEDIUM",
                    description="At least one prior month experienced a net cash deficit.",
                )
            )

        # Fallback if no adverse factors detected
        if not factors:
            f_name = "historical cash-flow pattern is comparatively stable"
            factors.append(f_name)
            factor_details.append(
                ShortfallFactorDetail(
                    factor=f_name,
                    severity="LOW",
                    description="Historical cash-flow patterns demonstrate broad stability across observed months.",
                )
            )

        if not actions and likely:
            actions.append("review variable spending before the next month begins")

        exp_net = getattr(forecast, "expected_net_cash", None) if forecast else None
        if shortfall_risk == "HIGH":
            if exp_net is not None and exp_net > 0:
                explanation = (
                    "Model 4 identifies high shortfall vulnerability next month. "
                    "While Model 1 projects positive baseline net cash, "
                    "historical spending volatility and commitment burden leave minimal resilience against unexpected outflows."
                )
            else:
                explanation = (
                    "Model 4 predicts a high likelihood of cash shortfall next month, "
                    "based on historical net cash deficits and expense pressure."
                )
        elif shortfall_risk == "MODERATE":
            if exp_net is not None and exp_net > 0:
                explanation = (
                    "Model 4 predicts moderate shortfall risk next month. "
                    "While projected net cash remains positive, spending fluctuations or recurring obligations could tighten available reserves."
                )
            else:
                explanation = (
                    "Model 4 predicts moderate shortfall risk next month, "
                    "indicating potential cash-flow tightening under variable spending fluctuations."
                )
        else:
            explanation = (
                "Model 4 predicts a low likelihood of cash shortfall next month, "
                "supported by stable cash-flow continuity and positive forecast margins."
            )

        return factors, actions, factor_details, explanation


@lru_cache(maxsize=1)
def get_shortfall_service() -> FinancialShortfallService:
    return FinancialShortfallService()
