from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.subscription import TransactionStatusSummaryResponse


class BnplCostItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_name: str = Field(description="BNPL provider name.", examples=["Slice"])
    monthly_bnpl_commitment: float = Field(description="Normalized monthly BNPL commitment.", examples=[1804.0])
    total_amount_borrowed: float = Field(description="Estimated amount borrowed across the BNPL plan.", examples=[9020.0])


class ActiveBnplResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_name: str = Field(description="BNPL provider or merchant name.", examples=["Flipkart Pay Later"])
    first_transaction_date: date = Field(description="Earliest observed BNPL transaction date for the provider.")
    latest_transaction_date: date = Field(description="Most recent observed BNPL transaction date for the provider.")
    number_of_installments: int = Field(description="Number of installments observed or inferred for the provider.", examples=[5])
    monthly_bnpl_commitment: float = Field(description="Average monthly BNPL commitment for the provider.", examples=[1804.0])
    total_amount_borrowed: float = Field(description="Estimated borrowed amount represented by the provider's BNPL plan.", examples=[9020.0])
    total_amount_paid: float = Field(description="Total amount paid across observed BNPL transactions.", examples=[9020.0])
    autopay_enabled: bool = Field(description="Whether autopay is enabled for the provider.", examples=[True])
    payment_frequency: str = Field(description="Dominant payment frequency for the BNPL plan.", examples=["Installment"])
    commitment_type: str = Field(description="Dominant commitment type for the BNPL plan.", examples=["Mandatory"])
    transaction_status_summary: TransactionStatusSummaryResponse = Field(
        description="Summary of transaction status outcomes for the provider.",
    )


class BnplSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active_provider_count: int = Field(description="Number of active BNPL providers.", examples=[4])
    total_active_bnpl_accounts: int = Field(description="Total active BNPL account count, aligned to provider groups.", examples=[4])
    monthly_bnpl_burden: float = Field(description="Total monthly BNPL burden.", examples=[7208.0])
    annual_bnpl_burden: float = Field(description="Estimated annual BNPL burden.", examples=[86496.0])
    average_bnpl_amount: float = Field(description="Average monthly BNPL commitment across active providers.", examples=[1802.0])
    highest_provider_exposure: BnplCostItemResponse | None = Field(default=None, description="Provider with the highest exposure.")
    lowest_provider_exposure: BnplCostItemResponse | None = Field(default=None, description="Provider with the lowest exposure.")


class PaymentStatisticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    successful_payments: int = Field(description="Number of successful BNPL payments.", examples=[12])
    failed_payments: int = Field(description="Number of failed BNPL payments.", examples=[1])
    pending_payments: int = Field(description="Number of pending BNPL payments.", examples=[0])
    success_rate: float = Field(description="Successful BNPL payment rate as a percentage.", examples=[92.31])
    autopay_coverage: float = Field(description="Share of active BNPL providers that use autopay as a percentage.", examples=[75.0])
    transaction_status_summary: TransactionStatusSummaryResponse = Field(
        description="Overall BNPL transaction status summary.",
    )


class FinancialStatisticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    monthly_financial_capacity: float = Field(description="Monthly financial capacity of the user.", examples=[92000.0])
    bnpl_to_capacity_ratio: float = Field(description="Ratio of BNPL burden to monthly financial capacity.", examples=[0.08])
    monthly_bnpl_burden_percent: float = Field(description="Monthly BNPL burden as a percentage of capacity.", examples=[8.0])
    bnpl_contribution_towards_financial_exposure: float = Field(
        description="BNPL contribution toward overall financial exposure as a percentage.",
        examples=[7.41],
    )


class BnplInsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    insight_type: str = Field(description="Business-rule insight label.", examples=["High BNPL Burden"])
    message: str = Field(description="Human-readable insight summary.", examples=["BNPL burden uses 18.4% of monthly financial capacity."])
    severity: str = Field(description="Insight severity level.", examples=["high"])
    confidence: float = Field(description="Confidence score between 0 and 1.", examples=[0.93])
    evidence: list[str] = Field(description="Supporting evidence used to generate the insight.")


class BnplIntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(description="Unique user identifier for the analyzed account.", examples=["U001"])
    bnpl_summary: BnplSummaryResponse = Field(description="Aggregate BNPL burden summary.")
    active_bnpl_accounts: list[ActiveBnplResponse] = Field(description="Detected active BNPL accounts grouped by provider.")
    payment_statistics: PaymentStatisticsResponse = Field(description="Overall BNPL payment performance statistics.")
    financial_statistics: FinancialStatisticsResponse = Field(description="BNPL impact relative to financial capacity.")
    bnpl_insights: list[BnplInsightResponse] = Field(description="Business-rule insights derived from the BNPL portfolio.")