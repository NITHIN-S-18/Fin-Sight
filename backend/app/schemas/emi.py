from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.subscription import TransactionStatusSummaryResponse


class EmiCostItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_name: str = Field(description="Merchant associated with the EMI commitment.", examples=["EV EMI"])
    loan_type: str = Field(description="Canonical EMI loan type.", examples=["Vehicle Loan"])
    monthly_emi_amount: float = Field(
        description="Estimated monthly EMI amount after frequency normalization.",
        examples=[18403.0],
    )
    total_amount_paid: float = Field(description="Total amount paid across the observed EMI records.", examples=[73612.0])


class ActiveEmiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_name: str = Field(description="Merchant name for the active EMI.", examples=["EV EMI"])
    loan_type: str = Field(description="Canonical loan type for the EMI.", examples=["Vehicle Loan"])
    first_emi_date: date = Field(description="Earliest observed EMI date for the merchant.")
    latest_emi_date: date = Field(description="Most recent observed EMI date for the merchant.")
    number_of_emi_payments: int = Field(description="Number of EMI payments recorded for the merchant.", examples=[12])
    monthly_emi_amount: float = Field(description="Average normalized monthly EMI amount.", examples=[18403.0])
    total_amount_paid: float = Field(description="Total amount paid across all observed EMI transactions.", examples=[220836.0])
    autopay_enabled: bool = Field(description="Whether autopay is enabled for the merchant.", examples=[True])
    payment_frequency: str = Field(description="Dominant EMI payment frequency.", examples=["Monthly"])
    commitment_type: str = Field(description="Dominant commitment type for the EMI.", examples=["Mandatory"])
    transaction_status_summary: TransactionStatusSummaryResponse = Field(
        description="Summary of transaction statuses for the merchant's EMI records.",
    )


class EmiSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active_emi_count: int = Field(description="Number of active EMI merchants.", examples=[4])
    monthly_emi_burden: float = Field(description="Estimated total monthly EMI burden.", examples=[42752.0])
    annual_emi_burden: float = Field(description="Estimated annual EMI burden.", examples=[513024.0])
    average_emi_amount: float = Field(description="Average monthly EMI amount across active EMIs.", examples=[10688.0])
    highest_emi: EmiCostItemResponse | None = Field(default=None, description="Highest monthly EMI commitment.")
    lowest_emi: EmiCostItemResponse | None = Field(default=None, description="Lowest monthly EMI commitment.")
    mandatory_emi_count: int = Field(description="Number of active EMIs classified as mandatory.", examples=[3])
    optional_emi_count: int = Field(description="Number of active EMIs classified as optional.", examples=[1])


class PaymentStatisticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    successful_payments: int = Field(description="Number of successful EMI payments.", examples=[14])
    failed_payments: int = Field(description="Number of failed EMI payments.", examples=[1])
    pending_payments: int = Field(description="Number of pending EMI payments.", examples=[0])
    payment_success_rate: float = Field(description="Successful EMI payment rate as a percentage.", examples=[93.33])
    autopay_coverage: float = Field(description="Share of active EMIs that use autopay as a percentage.", examples=[75.0])
    transaction_status_summary: TransactionStatusSummaryResponse = Field(
        description="Overall EMI transaction status summary.",
    )


class FinancialStatisticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    monthly_financial_capacity: float = Field(description="Monthly financial capacity of the user.", examples=[92000.0])
    monthly_emi_burden: float = Field(description="Monthly EMI burden used for financial analysis.", examples=[42752.0])
    annual_emi_burden: float = Field(description="Annualized EMI burden used for financial analysis.", examples=[513024.0])
    emi_to_monthly_capacity_ratio: float = Field(description="Ratio of EMI burden to monthly financial capacity.", examples=[0.46])
    monthly_emi_burden_percent: float = Field(description="Monthly EMI burden as a percentage of financial capacity.", examples=[46.47])
    contribution_of_emi_towards_financial_exposure: float = Field(
        description="Contribution of EMI obligations toward overall financial exposure as a percentage.",
        examples=[31.71],
    )


class EmiInsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    insight_type: str = Field(description="Business-rule insight label.", examples=["High Monthly EMI Burden"])
    message: str = Field(description="Human-readable insight summary.", examples=["Monthly EMI burden consumes 46.5% of monthly financial capacity."])
    severity: str = Field(description="Insight severity level.", examples=["high"])
    confidence: float = Field(description="Confidence score between 0 and 1.", examples=[0.93])
    evidence: list[str] = Field(description="Supporting evidence used to generate the insight.")


class EmiIntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(description="Unique user identifier for the analyzed account.", examples=["U001"])
    emi_summary: EmiSummaryResponse = Field(description="Aggregate EMI burden summary.")
    active_emis: list[ActiveEmiResponse] = Field(description="Detected active EMIs grouped by merchant.")
    payment_statistics: PaymentStatisticsResponse = Field(description="Overall EMI payment performance statistics.")
    financial_statistics: FinancialStatisticsResponse = Field(description="EMI impact relative to financial capacity.")
    emi_insights: list[EmiInsightResponse] = Field(description="Business-rule insights derived from the EMI portfolio.")