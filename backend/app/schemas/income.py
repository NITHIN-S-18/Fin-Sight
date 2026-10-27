from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


IncomeMode = Literal["auto", "manual", "expected"]
IncomeSourceLabel = Literal["Observed", "Estimated", "Manual"]


class IncomeConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(description="Financial user ID.")
    income_mode: IncomeMode = Field(
        default="auto",
        description="Active income mode: 'auto', 'manual', or 'expected'.",
    )
    manual_monthly_income: float | None = Field(
        default=None,
        description="Manually configured current monthly income in INR.",
    )
    expected_monthly_income: float | None = Field(
        default=None,
        description="Configured expected future monthly income in INR for planning and simulations.",
    )
    effective_date: date | None = Field(
        default=None,
        description="Optional effective date for manual or expected salary.",
    )
    effective_monthly_income: float = Field(
        description="Resolved effective current monthly income used across all financial calculations.",
    )
    income_source_label: IncomeSourceLabel = Field(
        description="Source label indicating how current income was derived ('Observed', 'Estimated', or 'Manual').",
    )
    auto_detected_income: float = Field(
        default=0.0,
        description="Baseline auto-detected or profile capacity.",
    )
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)


class IncomeConfigurationUpdateRequest(BaseModel):
    income_mode: IncomeMode = Field(
        default="auto",
        description="Income mode to set: 'auto', 'manual', or 'expected'.",
    )
    manual_monthly_income: float | None = Field(
        default=None,
        ge=0,
        le=1_000_000_000,
        description="Current monthly income (required if mode is 'manual').",
    )
    expected_monthly_income: float | None = Field(
        default=None,
        ge=0,
        le=1_000_000_000,
        description="Expected future monthly income (used for planning and What-If simulations).",
    )
    effective_date: date | None = Field(
        default=None,
        description="Optional effective date.",
    )

    @field_validator("manual_monthly_income")
    @classmethod
    def validate_manual_income(cls, v: float | None, info) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Monthly income cannot be negative.")
        return round(v, 2) if v is not None else None

    @field_validator("expected_monthly_income")
    @classmethod
    def validate_expected_income(cls, v: float | None, info) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Expected monthly income cannot be negative.")
        return round(v, 2) if v is not None else None
