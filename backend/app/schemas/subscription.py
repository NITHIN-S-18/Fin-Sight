from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SubscriptionCostItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_name: str = Field(description="Merchant associated with the subscription.", examples=["Netflix"])
    average_subscription_amount: float = Field(
        description="Average observed amount for the subscription.",
        examples=[555.0],
    )
    monthly_estimated_cost: float = Field(
        description="Estimated monthly cost after normalizing the subscription frequency.",
        examples=[555.0],
    )


class TransactionStatusSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status_breakdown: dict[str, int] = Field(
        description="Raw transaction status counts grouped by status label.",
        examples=[{"Success": 3, "Failed": 1}],
    )
    successful_transactions: int = Field(description="Number of successful transactions.", examples=[3])
    failed_transactions: int = Field(description="Number of failed transactions.", examples=[1])
    pending_transactions: int = Field(description="Number of pending or in-progress transactions.", examples=[0])
    other_transactions: int = Field(description="Number of transactions that do not fit the main buckets.", examples=[0])


class ActiveSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_name: str = Field(description="Merchant name for the active subscription.", examples=["Netflix"])
    first_subscription_date: date = Field(description="Earliest observed subscription date for the merchant.")
    latest_subscription_date: date = Field(description="Most recent observed subscription date for the merchant.")
    number_of_payments: int = Field(description="Number of payments recorded for the merchant.", examples=[4])
    average_subscription_amount: float = Field(
        description="Average transaction amount for the merchant.",
        examples=[555.0],
    )
    total_amount_paid: float = Field(description="Total paid across all observed subscription transactions.", examples=[2220.0])
    autopay_enabled: bool = Field(description="Whether autopay is enabled for the merchant.", examples=[True])
    recurring_frequency: str = Field(description="Dominant recurring frequency for the merchant.", examples=["Monthly"])
    merchant_type: str = Field(description="Dominant merchant type for the subscription.", examples=["OTT"])
    transaction_status_summary: TransactionStatusSummaryResponse = Field(
        description="Summary of transaction status outcomes for the merchant.",
    )


class NewSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    merchant_name: str = Field(description="Merchant that was newly activated.", examples=["Netflix"])
    subscription_date: date = Field(
        alias="date",
        description="Date when the new subscription was first observed.",
    )
    amount: float = Field(description="Amount charged when the subscription was activated.", examples=[555.0])


class TrialConversionCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_name: str = Field(description="Merchant suspected to have transitioned from trial to paid.", examples=["Adobe Creative Cloud"])
    possible_trial_conversion: bool = Field(
        description="Whether the transaction pattern looks like a possible trial-to-paid conversion.",
        examples=[True],
    )
    confidence_level: float = Field(description="Confidence score between 0 and 1 for the heuristic.", examples=[0.82])
    trial_start_date: date | None = Field(
        default=None,
        description="Date of the initial low-value or promotional trial transaction.",
    )
    paid_subscription_date: date | None = Field(
        default=None,
        description="Date of the later paid subscription transaction.",
    )
    initial_amount: float = Field(description="Initial trial or promotional amount.", examples=[0.0])
    recurring_paid_amount: float = Field(description="Later recurring paid amount.", examples=[932.0])
    evidence: str = Field(description="Short explanation for the heuristic result.", examples=["Zero-value first payment followed by paid monthly charges."])


class SubscriptionInsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    insight_type: str = Field(description="Business-rule insight label.", examples=["High Subscription Spending"])
    message: str = Field(description="Human-readable insight summary.", examples=["Subscription spending uses 22% of monthly financial capacity."])
    severity: str = Field(description="Insight severity level.", examples=["high"])
    confidence: float = Field(description="Confidence score between 0 and 1.", examples=[0.91])
    evidence: list[str] = Field(description="Supporting evidence used to generate the insight.")


class AutopayStatisticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_autopay_subscriptions: int = Field(description="Count of merchants with autopay enabled.", examples=[3])
    monthly_autopay_commitment: float = Field(description="Estimated monthly autopay commitment.", examples=[2125.0])
    annual_autopay_commitment: float = Field(description="Estimated annual autopay commitment.", examples=[25500.0])
    autopay_share_of_subscriptions: float = Field(
        description="Share of active subscriptions that use autopay.",
        examples=[0.6],
    )


class SubscriptionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscription_count: int = Field(description="Total number of active subscription merchants.", examples=[5])
    monthly_subscription_cost: float = Field(description="Estimated total monthly subscription cost.", examples=[4260.0])
    annual_subscription_cost: float = Field(description="Estimated total annual subscription cost.", examples=[51120.0])
    average_subscription_cost: float = Field(
        description="Average estimated monthly cost per active subscription.",
        examples=[852.0],
    )
    most_expensive_subscription: SubscriptionCostItemResponse | None = Field(
        default=None,
        description="Most expensive subscription after normalizing recurring frequency.",
    )
    least_expensive_subscription: SubscriptionCostItemResponse | None = Field(
        default=None,
        description="Least expensive subscription after normalizing recurring frequency.",
    )


class SubscriptionIntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(description="Unique user identifier for the analyzed account.", examples=["U001"])
    subscription_summary: SubscriptionSummaryResponse = Field(description="Aggregate subscription spending summary.")
    active_subscriptions: list[ActiveSubscriptionResponse] = Field(
        description="Detected active subscriptions grouped by merchant.",
    )
    new_subscriptions: list[NewSubscriptionResponse] = Field(
        description="Subscriptions flagged as newly activated in the transaction history.",
    )
    trial_conversion_candidates: list[TrialConversionCandidateResponse] = Field(
        description="Possible trial-to-paid conversion patterns detected in the history.",
    )
    subscription_insights: list[SubscriptionInsightResponse] = Field(
        description="Business-rule insights derived from the subscription portfolio.",
    )
    autopay_statistics: AutopayStatisticsResponse = Field(description="Autopay-related subscription statistics.")