from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

FREQUENCIES = {"weekly", "biweekly", "monthly", "quarterly", "annual"}
CATEGORIES = {
    "subscription", "emi", "bnpl", "rent", "insurance", "utility",
    "internet", "mobile", "membership", "education", "investment", "other",
}


def normalize_category(value: str) -> str:
    normalized = value.strip().lower().replace("-", " ").replace("_", " ")
    aliases = {
        "emi / loans": "emi",
        "loan": "emi",
        "loans": "emi",
        "memberships": "membership",
        "education fee": "education",
        "education fees": "education",
        "sip / investment": "investment",
        "sip / investments": "investment",
        "electricity": "utility",
        "water": "utility",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in CATEGORIES:
        raise ValueError("Unsupported recurring-payment category.")
    return normalized


class UserRecurringPaymentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    category: str
    amount: float = Field(gt=0)
    frequency: str
    next_expected_date: date
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank.")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        return normalize_category(value)

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in FREQUENCIES:
            raise ValueError("Frequency must be weekly, biweekly, monthly, quarterly, or annual.")
        return value


class UserRecurringPaymentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    category: str | None = None
    amount: float | None = Field(default=None, gt=0)
    frequency: str | None = None
    next_expected_date: date | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank.")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str | None) -> str | None:
        return normalize_category(value) if value is not None else None

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if value not in FREQUENCIES:
            raise ValueError("Frequency must be weekly, biweekly, monthly, quarterly, or annual.")
        return value


class RecurringPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str = Field(description="Normalized merchant or recurring-payment name.")
    category: str = Field(description="Generalized recurring-payment category.")
    amount: float = Field(description="Typical observed payment amount.")
    frequency: str = Field(description="Detected payment frequency.")
    monthly_equivalent_amount: float = Field(description="Estimated monthly equivalent amount.")
    last_payment_date: date | None = None
    next_expected_date: date | None = None
    status: str = Field(description="Lifecycle status of the detected pattern.")
    confidence: float = Field(ge=0, le=1)
    confidence_level: str = Field(description="High or low detection confidence.")
    source: str = Field(description="Detection source. Phase 1 records are DETECTED.")
    is_active: bool
    supporting_transaction_ids: list[str]
    evidence: dict[str, object]
    transactional_engagement_status: str | None = Field(
        default=None,
        description="Observed payment-engagement signal, not actual application usage.",
    )
    transactional_engagement_explanation: str | None = Field(default=None)


class CancellationSimulationRequest(BaseModel):
    goal_amount: float | None = Field(default=None, gt=0)
    timeframe_months: int | None = Field(default=None, ge=1, le=600)


class CancellationSimulationResponse(BaseModel):
    recurring_payment_id: int
    subscription_name: str
    current_monthly_subscription_commitment: float
    projected_monthly_subscription_commitment: float
    current_total_monthly_commitments: float
    projected_total_monthly_commitments: float
    current_monthly_expenses: float | None
    projected_monthly_expenses: float | None
    current_available_cash: float | None
    projected_available_cash: float | None
    additional_monthly_savings: float
    annual_potential_savings: float
    current_goal_feasible: bool | None = None
    projected_goal_feasible: bool | None = None
    cancellation_applied: bool = False
    explanation: str


class BatchCancellationSimulationRequest(BaseModel):
    recurring_payment_ids: list[int] = Field(default_factory=list)
    goal_id: int | None = None
    goal_amount: float | None = Field(default=None, gt=0)
    timeframe_months: int | None = Field(default=None, ge=1, le=600)


class GoalImpactDetail(BaseModel):
    goal_id: int | None = None
    goal_name: str | None = None
    target_amount: float | None = None
    timeframe_months: int | None = None
    required_monthly_saving: float | None = None
    current_available_cash: float | None = None
    projected_available_cash: float | None = None
    current_gap: float | None = None
    projected_gap: float | None = None
    gap_closed_percent: float | None = None
    current_goal_feasible: bool | None = None
    projected_goal_feasible: bool | None = None
    explanation: str


class SelectedSubscriptionDetail(BaseModel):
    id: int
    name: str
    category: str
    frequency: str
    original_amount: float
    monthly_equivalent_amount: float
    engagement_status: str | None = None


class BatchCancellationSimulationResponse(BaseModel):
    selected_count: int
    selected_subscriptions: list[SelectedSubscriptionDetail] = Field(default_factory=list)
    current_total_monthly_commitments: float
    projected_total_monthly_commitments: float
    current_monthly_subscription_commitment: float
    projected_monthly_subscription_commitment: float
    monthly_savings: float
    annual_potential_savings: float
    current_available_cash: float | None = None
    projected_available_cash: float | None = None
    goal_impact: GoalImpactDetail | None = None
    cancellation_applied: bool = False
    explanation: str


class RecurringPaymentListResponse(BaseModel):
    items: list[RecurringPaymentResponse]
    total: int

