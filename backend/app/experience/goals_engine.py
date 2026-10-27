from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.digital_twin.twin_engine import FinancialSnapshot


class GoalCategory(str, Enum):
    PRODUCT_PURCHASE = "product_purchase"
    VEHICLE = "vehicle"
    HOUSE = "house"
    EMERGENCY_FUND = "emergency_fund"
    VACATION = "vacation"
    OTHER = "other"


@dataclass(frozen=True)
class GoalProgress:
    """
    Data structure tracking goal completion progress.
    """

    current_amount: float
    target_amount: float
    remaining_amount: float
    percentage_completed: float


@dataclass
class GoalPlan:
    """
    Structured plan for achieving a financial goal.
    """

    goal_id: str
    title: str
    category: GoalCategory
    target_amount: float
    target_months: int
    monthly_savings_required: float
    is_affordable: bool
    progress: GoalProgress
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GoalRecommendation:
    """
    Actionable recommendation and feasibility analysis for a financial goal.
    """

    goal_id: str
    recommendation_text: str
    action_plan: list[str] = field(default_factory=list)
    feasible_without_loan: bool = True
    suggested_tenure_months: int = 12


class GoalsEngine:
    """
    Goals Engine.

    Evaluates user financial goals (product purchase, vehicle, house, emergency fund, vacation),
    estimates progress, remaining required savings, monthly requirements, and affordability
    based on current monthly liquid savings without persistence.
    """

    def evaluate_goal(
        self,
        snapshot: FinancialSnapshot,
        goal_title: str,
        target_amount: float,
        target_months: int,
        current_savings: float = 0.0,
        category: GoalCategory = GoalCategory.PRODUCT_PURCHASE,
    ) -> tuple[GoalPlan, GoalRecommendation]:
        """
        Evaluates a financial goal against a user's liquid savings capacity.
        Returns a tuple of (GoalPlan, GoalRecommendation).
        """
        target = max(0.0, float(target_amount))
        months = max(1, int(target_months))
        current = max(0.0, float(current_savings))

        remaining = max(0.0, target - current)
        pct_completed = round((current / target * 100.0) if target > 0 else 100.0, 2)

        progress = GoalProgress(
            current_amount=current,
            target_amount=target,
            remaining_amount=remaining,
            percentage_completed=min(100.0, pct_completed),
        )

        monthly_req = round(remaining / months, 2)
        available_monthly_savings = max(0.0, snapshot.monthly_savings)

        is_affordable = available_monthly_savings >= monthly_req
        goal_id = f"goal_{uuid.uuid4().hex[:8]}"

        plan = GoalPlan(
            goal_id=goal_id,
            title=goal_title,
            category=category,
            target_amount=target,
            target_months=months,
            monthly_savings_required=monthly_req,
            is_affordable=is_affordable,
            progress=progress,
            metadata={
                "user_id": snapshot.user_id,
                "available_monthly_savings": available_monthly_savings,
            },
        )

        # Build Action Plan & Recommendation Text
        action_plan: list[str] = []
        feasible_without_loan = True
        suggested_tenure = months

        if is_affordable:
            rec_text = (
                f"Goal '{goal_title}' is fully affordable! Allocate INR {monthly_req:.2f} per month "
                f"from your available monthly savings buffer (INR {available_monthly_savings:.2f})."
            )
            action_plan.append(f"Set up an automated monthly transfer of INR {monthly_req:.2f} to goal savings.")
            action_plan.append(f"Target completion expected in {months} months.")
        else:
            deficit = monthly_req - available_monthly_savings
            feasible_without_loan = False
            # Recalculate realistic tenure based on available monthly savings
            if available_monthly_savings > 0:
                suggested_tenure = int(remaining / available_monthly_savings) + 1
            else:
                suggested_tenure = months * 2

            rec_text = (
                f"Goal '{goal_title}' requires INR {monthly_req:.2f}/month, which exceeds your current monthly savings "
                f"buffer of INR {available_monthly_savings:.2f} by INR {deficit:.2f}/month."
            )
            action_plan.append(f"Extend goal timeline from {months} months to {suggested_tenure} months to fit current savings buffer.")
            action_plan.append("Alternatively, review discretionary commitments or cancel unused subscriptions to increase monthly savings buffer.")
            if category in (GoalCategory.PRODUCT_PURCHASE, GoalCategory.VEHICLE):
                action_plan.append("Consider no-cost EMI or down payment options if purchase cannot be delayed.")

        recommendation = GoalRecommendation(
            goal_id=goal_id,
            recommendation_text=rec_text,
            action_plan=action_plan,
            feasible_without_loan=feasible_without_loan,
            suggested_tenure_months=suggested_tenure,
        )

        return plan, recommendation
