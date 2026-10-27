from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any

from fastapi import Depends

from app.core.exceptions import (
    BnplNotFoundError,
    BnplProcessingError,
    DashboardProcessingError,
    EmiNotFoundError,
    EmiProcessingError,
    ExposureDataUnavailableError,
    ExposureNotFoundError,
    ExposureProcessingError,
    SubscriptionNotFoundError,
    SubscriptionProcessingError,
    UserNotFoundError,
)
from app.schemas.dataset import UserResponse
from app.schemas.dashboard import (
    DashboardAlert,
    DashboardCashFlowForecast,
    DashboardExposureCard,
    DashboardHealthCard,
    DashboardMetadata,
    DashboardQuickStats,
    DashboardResponse,
    DashboardOnboardingResponse,
    DashboardUpcomingCommitment,
    SubscriptionHighlights,
    EmiHighlights,
    BnplHighlights,
)
from app.services.bnpl_service import BnplService
from app.services.cashflow_forecast_service import CashFlowForecastService
from app.services.dataset_service import DatasetService, get_dataset_service
from app.services.emi_service import EmiService
from app.services.exposure_service import ExposureService, get_exposure_service
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(
        self,
        dataset_service: DatasetService,
        subscription_service: SubscriptionService,
        emi_service: EmiService,
        bnpl_service: BnplService,
        exposure_service: ExposureService,
        cashflow_service: CashFlowForecastService | None = None,
    ) -> None:
        self._dataset_service = dataset_service
        self._subscription_service = subscription_service
        self._emi_service = emi_service
        self._bnpl_service = bnpl_service
        self._exposure_service = exposure_service
        self._cashflow_service = cashflow_service or CashFlowForecastService(dataset_service)

    def get_dashboard_intelligence(self, user_id: str) -> DashboardResponse | DashboardOnboardingResponse:
        started_at = time.perf_counter()
        logger.info("Dashboard intelligence compilation started for user_id=%s", user_id)

        try:
            # 1. Retrieve the user record (raises UserNotFoundError if user is invalid)
            user_record = self._dataset_service.get_user(user_id)
            user_profile = UserResponse(**user_record)
            if not self._dataset_service.get_user_transactions(user_id):
                return DashboardOnboardingResponse(
                    user_profile=user_profile,
                    message="Upload a transaction CSV to unlock your financial dashboard.",
                    metadata=DashboardMetadata(
                        generated_at=datetime.now(timezone.utc),
                        execution_time_seconds=round(time.perf_counter() - started_at, 4),
                        data_sources=["DatasetService"],
                        api_version="v1",
                    ),
                )

            # 2. Query individual intelligence services safely
            try:
                subscription = self._subscription_service.get_subscription_intelligence(user_id)
            except SubscriptionNotFoundError:
                subscription = None

            try:
                emi = self._emi_service.get_emi_intelligence(user_id)
            except EmiNotFoundError:
                emi = None

            try:
                bnpl = self._bnpl_service.get_bnpl_intelligence(user_id)
            except BnplNotFoundError:
                bnpl = None

            # 3. Query the Exposure engine
            exposure = self._exposure_service.get_exposure_intelligence(user_id)

            # 4. Map Financial Health Card
            financial_health_card = DashboardHealthCard(
                financial_health_score=exposure.financial_health.financial_health_score,
                financial_health_label=exposure.financial_health.financial_health_label,
                risk_level=exposure.financial_health.risk_level,
                rationale=exposure.financial_health.rationale,
            )

            # 5. Map Exposure Card
            exposure_card = DashboardExposureCard(
                exposure_score=exposure.current_financial_status.exposure_score,
                exposure_band=exposure.exposure_summary.exposure_band,
                monthly_total_commitments=exposure.current_financial_status.monthly_total_commitments,
                monthly_financial_capacity=exposure.current_financial_status.monthly_financial_capacity,
                available_monthly_capacity=exposure.current_financial_status.available_monthly_capacity,
                explanation=exposure.exposure_summary.explanation,
                income_source=getattr(exposure.current_financial_status, "income_source", "Observed"),
                income_mode=getattr(exposure.current_financial_status, "income_mode", "auto"),
                expected_monthly_income=getattr(exposure.current_financial_status, "expected_monthly_income", None),
                manual_monthly_income=getattr(exposure.current_financial_status, "manual_monthly_income", None),
            )

            # 6. Map Commitment Summary
            commitment_summary = exposure.commitment_breakdown

            # 7. Compile Subscription Highlights
            if subscription:
                sub_highlights = SubscriptionHighlights(
                    active_count=subscription.subscription_summary.subscription_count,
                    monthly_cost=subscription.subscription_summary.monthly_subscription_cost,
                    most_expensive=subscription.subscription_summary.most_expensive_subscription,
                    autopay_coverage_percent=round(
                        subscription.autopay_statistics.autopay_share_of_subscriptions * 100.0, 2
                    ),
                    new_subscriptions_count=len(subscription.new_subscriptions),
                    trial_conversions_count=len(subscription.trial_conversion_candidates),
                )
            else:
                sub_highlights = SubscriptionHighlights(
                    active_count=0,
                    monthly_cost=0.0,
                    most_expensive=None,
                    autopay_coverage_percent=0.0,
                    new_subscriptions_count=0,
                    trial_conversions_count=0,
                )

            # 8. Compile EMI Highlights
            if emi:
                loan_types = sorted(list({x.loan_type for x in emi.active_emis if x.loan_type}))
                emi_highlights = EmiHighlights(
                    active_count=emi.emi_summary.active_emi_count,
                    monthly_burden=emi.emi_summary.monthly_emi_burden,
                    highest_emi=emi.emi_summary.highest_emi,
                    autopay_coverage_percent=emi.payment_statistics.autopay_coverage,
                    payment_success_rate=emi.payment_statistics.payment_success_rate,
                    loan_types=loan_types,
                )
            else:
                emi_highlights = EmiHighlights(
                    active_count=0,
                    monthly_burden=0.0,
                    highest_emi=None,
                    autopay_coverage_percent=0.0,
                    payment_success_rate=100.0,
                    loan_types=[],
                )

            # 9. Compile BNPL Highlights
            if bnpl:
                active_providers = sorted(list({x.provider_name for x in bnpl.active_bnpl_accounts if x.provider_name}))
                bnpl_highlights = BnplHighlights(
                    active_providers_count=bnpl.bnpl_summary.active_provider_count,
                    monthly_burden=bnpl.bnpl_summary.monthly_bnpl_burden,
                    highest_provider_exposure=bnpl.bnpl_summary.highest_provider_exposure,
                    autopay_coverage_percent=bnpl.payment_statistics.autopay_coverage,
                    payment_success_rate=bnpl.payment_statistics.success_rate,
                    active_providers=active_providers,
                )
            else:
                bnpl_highlights = BnplHighlights(
                    active_providers_count=0,
                    monthly_burden=0.0,
                    highest_provider_exposure=None,
                    autopay_coverage_percent=0.0,
                    payment_success_rate=100.0,
                    active_providers=[],
                )

            # 10. Map Top Recommendations
            top_recommendations = exposure.recommendations

            # 11. Compile Upcoming Commitments Chronologically
            upcoming_commitments: list[DashboardUpcomingCommitment] = []
            seen_events = set()

            def add_upcoming_event(title: str, expected_date: date | None, amount: float, source: str, f_type: str) -> None:
                event_key = (title, expected_date, amount, source)
                if event_key not in seen_events:
                    seen_events.add(event_key)
                    upcoming_commitments.append(
                        DashboardUpcomingCommitment(
                            title=title,
                            expected_date=expected_date,
                            amount=amount,
                            source=source,
                            type=f_type,
                        )
                    )

            forecast = exposure.financial_forecast
            for event in forecast.upcoming_trial_conversions:
                add_upcoming_event(
                    event.title, event.expected_date, event.expected_amount, event.source or "Subscription", event.forecast_type
                )
            for event in forecast.upcoming_paid_subscriptions:
                add_upcoming_event(
                    event.title, event.expected_date, event.expected_amount, event.source or "Subscription", event.forecast_type
                )
            for event in forecast.upcoming_emi_commencements:
                add_upcoming_event(
                    event.title, event.expected_date, event.expected_amount, event.source or "EMI", event.forecast_type
                )
            for event in forecast.upcoming_bnpl_installments:
                add_upcoming_event(
                    event.title, event.expected_date, event.expected_amount, event.source or "BNPL", event.forecast_type
                )

            upcoming_commitments.sort(key=lambda x: x.expected_date or date.max)

            # 12. Compile Dashboard Alerts
            dashboard_alerts: list[DashboardAlert] = []

            # Add Critical warnings from exposure/health available capacity
            if exposure.available_capacity.critical_warning:
                dashboard_alerts.append(
                    DashboardAlert(
                        alert_type="Critical",
                        message=exposure.available_capacity.critical_warning,
                        source="Health",
                    )
                )

            # Add Subscription insights
            if subscription:
                for insight in subscription.subscription_insights:
                    sev = insight.severity.lower()
                    alert_type = "Critical" if sev == "critical" else ("Warning" if sev in ("high", "medium") else "Info")
                    dashboard_alerts.append(
                        DashboardAlert(
                            alert_type=alert_type,
                            message=insight.message,
                            source="Subscription",
                        )
                    )

            # Add EMI insights and failed payment warnings
            if emi:
                for insight in emi.emi_insights:
                    sev = insight.severity.lower()
                    alert_type = "Critical" if sev == "critical" else ("Warning" if sev in ("high", "medium") else "Info")
                    dashboard_alerts.append(
                        DashboardAlert(
                            alert_type=alert_type,
                            message=insight.message,
                            source="EMI",
                        )
                    )
                if emi.payment_statistics.failed_payments > 0:
                    dashboard_alerts.append(
                        DashboardAlert(
                            alert_type="Critical",
                            message=f"Observed {emi.payment_statistics.failed_payments} failed EMI payments. Action required to avoid penalties.",
                            source="EMI",
                        )
                    )

            # Add BNPL insights and failed payment warnings
            if bnpl:
                for insight in bnpl.bnpl_insights:
                    sev = insight.severity.lower()
                    alert_type = "Critical" if sev == "critical" else ("Warning" if sev in ("high", "medium") else "Info")
                    dashboard_alerts.append(
                        DashboardAlert(
                            alert_type=alert_type,
                            message=insight.message,
                            source="BNPL",
                        )
                    )
                if bnpl.payment_statistics.failed_payments > 0:
                    dashboard_alerts.append(
                        DashboardAlert(
                            alert_type="Critical",
                            message=f"Observed {bnpl.payment_statistics.failed_payments} failed BNPL payments. Action required to prevent account suspension.",
                            source="BNPL",
                        )
                    )

            # 13. Compile Quick Statistics
            sub_count = subscription.subscription_summary.subscription_count if subscription else 0
            emi_count = emi.emi_summary.active_emi_count if emi else 0
            bnpl_count = bnpl.bnpl_summary.active_provider_count if bnpl else 0
            total_commitments_count = sub_count + emi_count + bnpl_count

            sub_monthly = subscription.subscription_summary.monthly_subscription_cost if subscription else 0.0
            emi_monthly = emi.emi_summary.monthly_emi_burden if emi else 0.0
            bnpl_monthly = bnpl.bnpl_summary.monthly_bnpl_burden if bnpl else 0.0
            if exposure and exposure.current_financial_status:
                monthly_commitments_total = exposure.current_financial_status.monthly_total_commitments
            else:
                monthly_commitments_total = sub_monthly + emi_monthly + bnpl_monthly

            financial_capacity = exposure.current_financial_status.monthly_financial_capacity
            available_capacity = exposure.current_financial_status.available_monthly_capacity
            available_capacity_percentage = (
                round((available_capacity / financial_capacity) * 100.0, 2) if financial_capacity > 0 else 0.0
            )

            # Combined payment success and autopay stats
            successful = 0
            failed = 0
            pending = 0
            autopay_count = 0
            active_commitments = 0

            if subscription:
                for item in subscription.active_subscriptions:
                    ts = item.transaction_status_summary
                    successful += ts.successful_transactions
                    failed += ts.failed_transactions
                    pending += ts.pending_transactions
                    if item.autopay_enabled:
                        autopay_count += 1
                active_commitments += len(subscription.active_subscriptions)

            if emi:
                successful += emi.payment_statistics.successful_payments
                failed += emi.payment_statistics.failed_payments
                pending += emi.payment_statistics.pending_payments
                autopay_count += sum(1 for x in emi.active_emis if x.autopay_enabled)
                active_commitments += len(emi.active_emis)

            if bnpl:
                successful += bnpl.payment_statistics.successful_payments
                failed += bnpl.payment_statistics.failed_payments
                pending += bnpl.payment_statistics.pending_payments
                autopay_count += sum(1 for x in bnpl.active_bnpl_accounts if x.autopay_enabled)
                active_commitments += len(bnpl.active_bnpl_accounts)

            total_events = successful + failed + pending
            overall_payment_success_rate = (
                round((successful / total_events) * 100.0, 2) if total_events > 0 else 100.0
            )
            overall_autopay_coverage = (
                round((autopay_count / active_commitments) * 100.0, 2) if active_commitments > 0 else 100.0
            )

            quick_statistics = DashboardQuickStats(
                total_commitments_count=total_commitments_count,
                monthly_commitments_total=round(monthly_commitments_total, 2),
                financial_capacity=round(financial_capacity, 2),
                available_capacity=round(available_capacity, 2),
                available_capacity_percentage=available_capacity_percentage,
                overall_payment_success_rate=overall_payment_success_rate,
                overall_autopay_coverage=overall_autopay_coverage,
                income_source=getattr(exposure.current_financial_status, "income_source", "Observed"),
                income_mode=getattr(exposure.current_financial_status, "income_mode", "auto"),
            )

            # 14. Model 1 Cash Flow Forecast Integration
            cash_flow_forecast: DashboardCashFlowForecast | None = None
            try:
                forecast_res = self._cashflow_service.forecast(user_id)
                if forecast_res.forecast_available and forecast_res.expected_variable_expenses is not None:
                    exp_var = forecast_res.expected_variable_expenses
                    calc_balance = round(
                        exposure_card.monthly_financial_capacity
                        - exposure_card.monthly_total_commitments
                        - exp_var,
                        2,
                    )
                    cash_flow_forecast = DashboardCashFlowForecast(
                        forecast_month=forecast_res.forecast_month,
                        forecast_available=True,
                        availability_status=forecast_res.availability_status,
                        history_months_available=forecast_res.history_months_available,
                        expected_variable_expenses=forecast_res.expected_variable_expenses,
                        expected_income=forecast_res.expected_income,
                        expected_total_expenses=forecast_res.expected_total_expenses,
                        available_balance=calc_balance,
                    )
                else:
                    cash_flow_forecast = DashboardCashFlowForecast(
                        forecast_month=forecast_res.forecast_month,
                        forecast_available=False,
                        availability_status=forecast_res.availability_status,
                        history_months_available=forecast_res.history_months_available,
                        expected_variable_expenses=None,
                        expected_income=None,
                        expected_total_expenses=None,
                        available_balance=None,
                    )
            except Exception:
                logger.info("Cash flow forecast unavailable for user_id=%s in dashboard", user_id)
                cash_flow_forecast = None

            # 15. Compile Metadata
            metadata = DashboardMetadata(
                generated_at=datetime.now(timezone.utc),
                execution_time_seconds=round(time.perf_counter() - started_at, 3),
                data_sources=["DatasetService", "SubscriptionService", "EMIService", "BNPLService", "ExposureService", "CashFlowForecastService"],
                api_version="v1",
            )

            return DashboardResponse(
                user_profile=user_profile,
                financial_health_card=financial_health_card,
                exposure_card=exposure_card,
                commitment_summary=commitment_summary,
                subscription_highlights=sub_highlights,
                emi_highlights=emi_highlights,
                bnpl_highlights=bnpl_highlights,
                top_recommendations=top_recommendations,
                upcoming_commitments=upcoming_commitments,
                dashboard_alerts=dashboard_alerts,
                quick_statistics=quick_statistics,
                cash_flow_forecast=cash_flow_forecast,
                metadata=metadata,
            )

        except UserNotFoundError:
            raise
        except ExposureDataUnavailableError:
            raise
        except (SubscriptionProcessingError, EmiProcessingError, BnplProcessingError, ExposureProcessingError):
            raise
        except Exception as exc:
            logger.exception("Dashboard intelligence compilation failed for user_id=%s", user_id)
            raise DashboardProcessingError(
                f"Unable to compile dashboard intelligence for user: {user_id}"
            ) from exc


@lru_cache(maxsize=1)
def get_dashboard_service(
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> DashboardService:
    if not isinstance(dataset_service, DatasetService):
        dataset_service = get_dataset_service()
    subscription_service = SubscriptionService(dataset_service)
    emi_service = EmiService(dataset_service)
    bnpl_service = BnplService(dataset_service)
    exposure_service = ExposureService(
        dataset_service=dataset_service,
        subscription_service=subscription_service,
        emi_service=emi_service,
        bnpl_service=bnpl_service,
    )
    cashflow_service = CashFlowForecastService(dataset_service)
    return DashboardService(
        dataset_service=dataset_service,
        subscription_service=subscription_service,
        emi_service=emi_service,
        bnpl_service=bnpl_service,
        exposure_service=exposure_service,
        cashflow_service=cashflow_service,
    )
