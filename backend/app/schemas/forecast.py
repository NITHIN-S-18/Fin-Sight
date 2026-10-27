from datetime import datetime

from pydantic import BaseModel, Field


class ForecastTargetMetrics(BaseModel):
    mae: float
    rmse: float
    r2: float
    median_absolute_error: float
    percentile_90_absolute_error: float
    improvement_over_baseline_percent: float | None = None


class CashFlowForecastResponse(BaseModel):
    user_id: str
    forecast_month: str
    forecast_available: bool
    availability_status: str
    history_months_available: int
    expected_income: float | None
    expected_committed_expenses: float | None
    expected_variable_expenses: float | None
    expected_total_expenses: float | None
    expected_net_cash: float | None
    selected_baselines: dict[str, str] = Field(default_factory=dict)
    model_version: str = "baseline"
    model_type: str = "baseline"
    data_cutoff: str | None = None
    variable_category_forecast: dict[str, float] = Field(default_factory=dict)
    evaluation: dict[str, ForecastTargetMetrics] = Field(default_factory=dict)
    split_metadata: dict[str, object] = Field(default_factory=dict)
    generated_at: datetime
