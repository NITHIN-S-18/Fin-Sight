from __future__ import annotations

from datetime import datetime
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GoalRequest(BaseModel):
    goal_amount: float = Field(..., gt=0, description="Total amount to save.")
    timeframe_months: int = Field(..., ge=1, le=600, description="Months available to reach the goal.")

    @field_validator("goal_amount")
    @classmethod
    def validate_finite_goal_amount(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Goal amount must be a finite number.")
        return value


class GoalCreateRequest(GoalRequest):
    goal_name: str = Field(..., min_length=1, max_length=120, description="Meaningful user-facing goal name.")

    @field_validator("goal_name")
    @classmethod
    def validate_goal_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Goal name cannot be blank.")
        return value


class CategoryAdjustment(BaseModel):
    category: str
    current_expected_spending: float
    observed_monthly_spending: float | None = None
    spending_basis: str = "legacy_persisted_evaluation"
    maximum_supported_reduction: float | None = None
    suggested_reduction: float
    adjusted_spending: float
    reduction_percent: float
    remaining_category_spending: float
    remaining_goal_savings_gap: float | None = None
    evidence: str = "This saved evaluation predates category-level recommendation evidence."
    protected: bool = False


class GoalEvaluation(BaseModel):
    user_id: str
    goal_amount: float
    goal_months: int
    required_monthly_saving: float | None = None
    expected_monthly_saving: float | None = None
    additional_monthly_saving_required: float | None = None
    goal_feasible: bool | None = None
    variable_spending_adjustment_required: float | None = None
    suggested_category_adjustments: list[CategoryAdjustment] = Field(default_factory=list)
    projected_variable_expenses_after_adjustment: float | None = None
    projected_monthly_saving_after_adjustment: float | None = None
    remaining_money_after_goal_saving: float | None = None
    explanation: str
    model_version: str = "model-2-baseline-v1"
    availability_status: str
    evaluation_metadata: dict[str, object] = Field(default_factory=dict)
    planned_monthly_contribution: float | None = None
    money_remaining_after_planned_contribution: float | None = None
    remaining_goal_savings_gap_after_plan: float | None = None


class FinancialGoalResponse(GoalEvaluation):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class GoalListResponse(BaseModel):
    items: list[FinancialGoalResponse] = Field(default_factory=list)


class GoalUpdateRequest(BaseModel):
    goal_name: str | None = Field(default=None, min_length=1, max_length=120)
    goal_amount: float | None = Field(default=None, gt=0)
    timeframe_months: int | None = Field(default=None, ge=1, le=600)
    planned_monthly_contribution: float | None = Field(default=None, ge=0)

    @field_validator("goal_amount")
    @classmethod
    def validate_finite_updated_goal_amount(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(value):
            raise ValueError("Goal amount must be a finite number.")
        return value

    @field_validator("planned_monthly_contribution")
    @classmethod
    def validate_finite_planned_contribution(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(value):
            raise ValueError("Planned monthly contribution must be a finite number.")
        return value

    @field_validator("goal_name")
    @classmethod
    def validate_updated_goal_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Goal name cannot be blank.")
        return value
