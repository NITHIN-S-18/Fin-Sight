from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DateRangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start_date: date | None = Field(description="Earliest transaction date in the dataset.", examples=["2023-12-30"])
    end_date: date | None = Field(description="Latest transaction date in the dataset.", examples=["2024-02-13"])


class UserFinancialProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(description="Unique user identifier.", examples=["U001"])
    persona: str = Field(description="User persona or segment.", examples=["Salaried Professionals"])
    monthly_financial_capacity: float = Field(description="Approximate monthly financial capacity.", examples=[92000.0])
    monthly_commitments: float = Field(description="Total monthly commitment amount.", examples=[12165.83])
    exposure_score: float = Field(description="Financial exposure score.", examples=[13.2])
    active_subscriptions: int = Field(description="Number of active subscriptions.", examples=[4])
    active_emis: int = Field(description="Number of active EMI commitments.", examples=[2])
    active_bnpl: int = Field(description="Number of active BNPL commitments.", examples=[3])
    total_active_commitments: int = Field(description="Total active commitments across product types.", examples=[9])
    total_transactions: int = Field(description="Total transactions observed for the user.", examples=[113])
    transaction_success_rate: str = Field(description="Transaction success rate as recorded in the dataset.", examples=["95.6%"])
    financial_health: str = Field(description="Pre-computed financial health classification from the dataset snapshot. This is a static value and may differ from the live-calculated health label returned by the Exposure Engine.", examples=["Healthy"])
    is_leakage_user: str = Field(description="Whether the user shows leakage behavior.", examples=["Yes"])
    leakage_subscription_count: int = Field(description="Count of leakage subscriptions.", examples=[2])
    is_heavy_bnpl_user: str = Field(description="Whether the user is a heavy BNPL user.", examples=["Yes"])
    heavy_bnpl_providers: int = Field(description="Number of heavy BNPL providers.", examples=[2])
    is_heavy_emi_user: str = Field(description="Whether the user is a heavy EMI user.", examples=["Yes"])
    heavy_emi_providers: int = Field(description="Number of heavy EMI providers.", examples=[2])
    special_scenario: str = Field(description="Human-readable scenario label.", examples=["Leakage User + Heavy BNPL User + Heavy EMI User"])


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(description="Unique user identifier.", examples=["U007"])
    persona: str | None = Field(default=None, description="User persona or segment.", examples=["Salaried Professionals"])
    income_type: str | None = Field(default=None, description="Income source type.", examples=["Fixed"])
    monthly_financial_capacity: int | float | None = Field(default=None, description="Approximate monthly financial capacity.", examples=[92000])
    age_group: str | None = Field(default=None, description="User age band.", examples=["22-34"])
    city: str | None = Field(default=None, description="Home city of the user.", examples=["Delhi"])
    financial_profile: UserFinancialProfileResponse | None = Field(
        default=None,
        description="Detailed financial exposure profile when available.",
    )


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str = Field(description="Unique transaction identifier.", examples=["TXN000001"])
    user_id: str = Field(description="Identifier of the user that generated the transaction.", examples=["U169"])
    transaction_date: date = Field(description="Transaction date.", examples=["2024-01-01"])
    merchant_name: str | None = Field(default=None, description="Merchant or product name.", examples=["Netflix"])
    description: str | None = Field(default=None, description="Original transaction description.", examples=["Netflix monthly subscription"])
    amount: float = Field(description="Transaction amount.", examples=[555.0])
    category: str | None = Field(default=None, description="Normalized category.", examples=["OTT"])
    transaction_class: str | None = Field(default=None, description="High-level transaction class.", examples=["Subscription"])
    payment_mode: str | None = Field(default=None, description="Payment instrument or channel.", examples=["Card AutoDebit"])
    frequency: str | None = Field(default=None, description="Frequency of the commitment.", examples=["Monthly"])
    income_flag: str | None = Field(default=None, description="Whether the transaction is income-related.", examples=["No"])
    recurring_flag: str | None = Field(default=None, description="Whether the transaction is recurring.", examples=["Yes"])
    autopay_flag: str | None = Field(default=None, description="Whether autopay is enabled.", examples=["Yes"])
    risk_label: str | None = Field(default=None, description="Risk label associated with the transaction.", examples=["Low"])
    transaction_status: str | None = Field(default=None, description="Processing status of the transaction.", examples=["Success"])
    is_new_subscription: str | None = Field(default=None, description="Whether the transaction is a new subscription.", examples=["Yes"])
    merchant_type: str | None = Field(default=None, description="Merchant type or business domain.", examples=["OTT"])
    commitment_type: str | None = Field(default=None, description="Commitment classification.", examples=["Optional"])


class DatasetSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_users: int = Field(description="Total number of users loaded from users.csv.", examples=[250])
    total_transactions: int = Field(description="Total number of transactions loaded from finsight_dataset_v2.csv.", examples=[318])
    date_range: DateRangeResponse = Field(description="Observed transaction date range.")
    persona_distribution: dict[str, int] = Field(description="Counts grouped by persona.")
    transaction_class_distribution: dict[str, int] = Field(description="Counts grouped by transaction class.")
    risk_distribution: dict[str, int] = Field(description="Counts grouped by risk label.")
    autopay_distribution: dict[str, int] = Field(description="Counts grouped by autopay flag.")


class DatasetHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = Field(description="Dataset module health status.", examples=["ok"])
    loaded: bool = Field(description="Whether all required dataset files loaded successfully.", examples=[True])
    loaded_at: datetime | None = Field(
        default=None,
        description="Timestamp when the datasets were loaded.",
    )
    records: dict[str, int] = Field(description="Record counts for each dataset.")
