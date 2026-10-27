from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HistoricalMetricPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    month: str = Field(description="Calendar month in YYYY-MM format.")
    income: float = Field(description="Successful income transactions for the month.")
    spending: float = Field(description="Successful non-income, non-commitment spending for the month.")
    commitments: float = Field(description="Successful subscription, EMI, and BNPL payments for the month.")
    exposure: float | None = Field(description="Commitments divided by income, expressed as a percentage.")
    financial_health: float | None = Field(
        description="Transaction-only health score derived from monthly exposure; null when income is unavailable."
    )
    available_capacity: float | None = Field(
        description="Income less commitments; null when income is unavailable."
    )


class HistoricalDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    points: list[HistoricalMetricPoint]
    metric_basis: str = Field(
        description="How the historical series was calculated and its limitations."
    )
