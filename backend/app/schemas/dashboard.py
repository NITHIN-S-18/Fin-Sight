from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.dataset import UserResponse
from app.schemas.exposure import (
    CommitmentBreakdownResponse,
    ExposureRecommendationResponse,
)
from app.schemas.subscription import SubscriptionCostItemResponse
from app.schemas.emi import EmiCostItemResponse
from app.schemas.bnpl import BnplCostItemResponse


class DashboardHealthCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    financial_health_score: float = Field(
        ...,
        description="Deterministic financial health score (0-100).",
        examples=[94.0],
    )
    financial_health_label: str = Field(
        ...,
        description="Live-calculated health classification from the Exposure Engine (e.g. Excellent, Healthy, Moderate, Risky, Critical). This is the authoritative health label derived from multiple factors.",
        examples=["Excellent"],
    )
    risk_level: str = Field(
        ...,
        description="Overall risk level (e.g. Low, Medium).",
        examples=["Low"],
    )
    rationale: list[str] = Field(
        ...,
        description="Key bullet points justifying the health score.",
        examples=[["Exposure score is 1.28%.", "Payment success rate is 100.0%."]],
    )


class DashboardExposureCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exposure_score: float = Field(
        ...,
        description="Financial exposure score (percentage).",
        examples=[1.28],
    )
    exposure_band: str = Field(
        ...,
        description="Standardized exposure band.",
        examples=["Low"],
    )
    monthly_total_commitments: float = Field(
        ...,
        description="Total monthly commitment across all products.",
        examples=[1996.0],
    )
    monthly_financial_capacity: float = Field(
        ...,
        description="Monthly financial capacity.",
        examples=[156000.0],
    )
    available_monthly_capacity: float = Field(
        ...,
        description="Remaining monthly capacity after current commitments.",
        examples=[154004.0],
    )
    explanation: str = Field(
        ...,
        description="Explanation of the exposure status.",
        examples=["Monthly commitments remain within monthly financial capacity."],
    )
    income_source: str = Field(
        default="Observed",
        description="Source label of the income (Observed, Estimated, or Manual).",
        examples=["Observed"],
    )
    income_mode: str = Field(
        default="auto",
        description="Active income configuration mode.",
        examples=["auto"],
    )
    expected_monthly_income: float | None = Field(
        default=None,
        description="Configured expected future monthly income if any.",
        examples=[85000.0],
    )
    manual_monthly_income: float | None = Field(
        default=None,
        description="Configured manual monthly income if any.",
        examples=[75000.0],
    )


class SubscriptionHighlights(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active_count: int = Field(
        ...,
        description="Total number of active subscriptions.",
        examples=[5],
    )
    monthly_cost: float = Field(
        ...,
        description="Total monthly subscription cost.",
        examples=[4260.0],
    )
    most_expensive: SubscriptionCostItemResponse | None = Field(
        default=None,
        description="Most expensive subscription after frequency normalization.",
    )
    autopay_coverage_percent: float = Field(
        ...,
        description="Share of active subscriptions that use autopay as a percentage.",
        examples=[60.0],
    )
    new_subscriptions_count: int = Field(
        ...,
        description="Number of new subscriptions detected in the transaction history.",
        examples=[1],
    )
    trial_conversions_count: int = Field(
        ...,
        description="Number of possible trial conversions detected.",
        examples=[0],
    )


class EmiHighlights(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active_count: int = Field(
        ...,
        description="Total number of active EMIs.",
        examples=[2],
    )
    monthly_burden: float = Field(
        ...,
        description="Total monthly EMI burden.",
        examples=[18403.0],
    )
    highest_emi: EmiCostItemResponse | None = Field(
        default=None,
        description="Highest monthly EMI commitment.",
    )
    autopay_coverage_percent: float = Field(
        ...,
        description="Percentage of EMIs using AutoPay.",
        examples=[75.0],
    )
    payment_success_rate: float = Field(
        ...,
        description="Successful EMI payment rate as a percentage.",
        examples=[93.33],
    )
    loan_types: list[str] = Field(
        ...,
        description="List of unique loan types active for the user.",
        examples=[["Vehicle Loan"]],
    )


class BnplHighlights(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active_providers_count: int = Field(
        ...,
        description="Number of active BNPL providers.",
        examples=[1],
    )
    monthly_burden: float = Field(
        ...,
        description="Total monthly BNPL burden.",
        examples=[1804.0],
    )
    highest_provider_exposure: BnplCostItemResponse | None = Field(
        default=None,
        description="Provider with the highest exposure.",
    )
    autopay_coverage_percent: float = Field(
        ...,
        description="Percentage of BNPL providers using AutoPay.",
        examples=[100.0],
    )
    payment_success_rate: float = Field(
        ...,
        description="Successful BNPL payment rate as a percentage.",
        examples=[100.0],
    )
    active_providers: list[str] = Field(
        ...,
        description="List of names of active BNPL providers.",
        examples=[["Simpl"]],
    )


class DashboardUpcomingCommitment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str = Field(
        ...,
        description="Event title.",
        examples=["EV EMI installment due"],
    )
    expected_date: date | None = Field(
        default=None,
        description="Expected date of the event.",
        examples=["2024-02-15"],
    )
    amount: float = Field(
        ...,
        description="Expected payment amount.",
        examples=[18403.0],
    )
    source: str = Field(
        ...,
        description="Commitment type (Subscription, EMI, BNPL).",
        examples=["EMI"],
    )
    type: str = Field(
        ...,
        description="Specific forecast type.",
        examples=["Upcoming EMI Installment"],
    )


class DashboardAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_type: str = Field(
        ...,
        description="Alert severity level (Critical, Warning, Info).",
        examples=["Warning"],
    )
    message: str = Field(
        ...,
        description="Alert message.",
        examples=["BNPL burden consumes 18.4% of monthly capacity."],
    )
    source: str = Field(
        ...,
        description="Source of the alert (Health, Subscription, EMI, BNPL).",
        examples=["BNPL"],
    )


class DashboardQuickStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_commitments_count: int = Field(
        ...,
        description="Total count of all active commitments.",
        examples=[8],
    )
    monthly_commitments_total: float = Field(
        ...,
        description="Sum of monthly commitments.",
        examples=[24467.0],
    )
    financial_capacity: float = Field(
        ...,
        description="Monthly financial capacity.",
        examples=[156000.0],
    )
    available_capacity: float = Field(
        ...,
        description="Available capacity after commitments.",
        examples=[131533.0],
    )
    available_capacity_percentage: float = Field(
        ...,
        description="Percentage of capacity available.",
        examples=[84.32],
    )
    overall_payment_success_rate: float = Field(
        ...,
        description="Weighted/combined successful payment rate.",
        examples=[95.0],
    )
    overall_autopay_coverage: float = Field(
        ...,
        description="Overall AutoPay coverage across commitments.",
        examples=[80.0],
    )
    income_source: str = Field(
        default="Observed",
        description="Source label of the income (Observed, Estimated, or Manual).",
        examples=["Observed"],
    )
    income_mode: str = Field(
        default="auto",
        description="Active income configuration mode.",
        examples=["auto"],
    )


class DashboardMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime = Field(
        ...,
        description="Timestamp when the dashboard was generated.",
    )
    execution_time_seconds: float = Field(
        ...,
        description="Total execution time for the dashboard compilation.",
        examples=[0.05],
    )
    data_sources: list[str] = Field(
        ...,
        description="Data sources included in the dashboard.",
        examples=[["DatasetService", "SubscriptionService", "EMIService", "BNPLService", "ExposureService"]],
    )
    api_version: str = Field(
        ...,
        description="API version.",
        examples=["v1"],
    )


class DashboardCashFlowForecast(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    forecast_month: str = Field(
        ...,
        description="Target forecast month.",
        examples=["2026-01"],
    )
    forecast_available: bool = Field(
        ...,
        description="Whether a valid Model 1 forecast is available.",
        examples=[True],
    )
    availability_status: str = Field(
        ...,
        description="Forecast availability status (available, insufficient_history, unavailable).",
        examples=["available"],
    )
    history_months_available: int = Field(
        ...,
        description="Number of historical transaction months available for training/evaluation.",
        examples=[15],
    )
    expected_variable_expenses: float | None = Field(
        default=None,
        description="Model 1 forecasted variable expenses for the upcoming month.",
        examples=[20332.87],
    )
    expected_income: float | None = Field(
        default=None,
        description="Model 1 forecasted income.",
        examples=[85000.0],
    )
    expected_total_expenses: float | None = Field(
        default=None,
        description="Model 1 forecasted total expenses (commitments + variable).",
        examples=[40953.87],
    )
    available_balance: float | None = Field(
        default=None,
        description="Authoritative available balance: capacity - commitments - variable expenses.",
        examples=[44046.13],
    )


class DashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_profile: UserResponse = Field(
        ...,
        description="User demographic and segment profile.",
    )
    financial_health_card: DashboardHealthCard = Field(
        ...,
        description="Financial health summary and rationale.",
    )
    exposure_card: DashboardExposureCard = Field(
        ...,
        description="Financial exposure metrics.",
    )
    commitment_summary: CommitmentBreakdownResponse = Field(
        ...,
        description="Breakdown of commitments by product type.",
    )
    subscription_highlights: SubscriptionHighlights = Field(
        ...,
        description="Subscription intelligence summary highlights.",
    )
    emi_highlights: EmiHighlights = Field(
        ...,
        description="EMI intelligence summary highlights.",
    )
    bnpl_highlights: BnplHighlights = Field(
        ...,
        description="BNPL intelligence summary highlights.",
    )
    top_recommendations: list[ExposureRecommendationResponse] = Field(
        ...,
        description="Prioritized recommendations to improve financial health.",
    )
    upcoming_commitments: list[DashboardUpcomingCommitment] = Field(
        ...,
        description="Chronological upcoming commitment payments.",
    )
    dashboard_alerts: list[DashboardAlert] = Field(
        ...,
        description="Actionable alerts or warnings.",
    )
    quick_statistics: DashboardQuickStats = Field(
        ...,
        description="Quick summary statistics.",
    )
    cash_flow_forecast: DashboardCashFlowForecast | None = Field(
        default=None,
        description="Model 1 cash flow forecast integration with variable expenses and available balance.",
    )
    metadata: DashboardMetadata = Field(
        ...,
        description="Response metadata.",
    )


class DashboardOnboardingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_profile: UserResponse
    onboarding_required: bool = True
    message: str
    metadata: DashboardMetadata
