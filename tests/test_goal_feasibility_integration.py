from __future__ import annotations

from app.services.cashflow_forecast_service import CashFlowForecastService
from app.services.goal_feasibility_service import GoalFeasibilityService
from app.schemas.goals import GoalCreateRequest, GoalRequest
from app.main import app
from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.database.models.financial_goal import FinancialGoal
from fastapi.testclient import TestClient
from uuid import uuid4
from types import SimpleNamespace
from pydantic import ValidationError
import pytest


def _transactions() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for month in range(1, 7):
        date = f"2025-{month:02d}"
        rows.extend(
            [
                {
                    "user_id": "runtime-user",
                    "transaction_date": f"{date}-01",
                    "amount": 50000,
                    "transaction_status": "Success",
                    "income_flag": True,
                    "transaction_class": "income",
                    "category": "Salary",
                },
                {
                    "user_id": "runtime-user",
                    "transaction_date": f"{date}-10",
                    "amount": 10000,
                    "transaction_status": "Success",
                    "income_flag": False,
                    "transaction_class": "emi",
                    "category": "Rent",
                },
                {
                    "user_id": "runtime-user",
                    "transaction_date": f"{date}-20",
                    "amount": 5000,
                    "transaction_status": "Success",
                    "income_flag": False,
                    "transaction_class": "food",
                    "category": "Food",
                },
            ]
        )
    return rows


class _Dataset:
    def get_user_transactions(self, user_id: str) -> list[dict[str, object]]:
        assert user_id == "runtime-user"
        return _transactions()


def test_goal_feasibility_consumes_six_month_forecast_contract_without_committed_key_error() -> None:
    dataset = _Dataset()
    forecast_service = CashFlowForecastService(dataset)
    forecast = forecast_service.forecast("runtime-user")

    assert forecast.forecast_available is True
    assert forecast.expected_income == 50000
    assert forecast.expected_committed_expenses == 10000
    assert forecast.expected_variable_expenses is not None
    assert forecast.expected_variable_expenses >= 0
    assert forecast.expected_total_expenses == round(
        forecast.expected_committed_expenses + forecast.expected_variable_expenses,
        2,
    )
    assert forecast.expected_net_cash == round(
        forecast.expected_income - forecast.expected_total_expenses,
        2,
    )

    goal_service = GoalFeasibilityService(dataset, forecast_service)
    result = goal_service.evaluate(
        "runtime-user",
        GoalRequest(goal_amount=30000, timeframe_months=3),
    )

    assert result.required_monthly_saving == 10000
    assert result.expected_monthly_saving == forecast.expected_net_cash
    assert result.projected_monthly_saving_after_adjustment is not None
    assert result.model_version in {"model-2-phase-c-v2", "model-2-baseline-v1"}


@pytest.mark.parametrize("amount", [float("inf"), float("nan"), -1, 0])
def test_goal_request_rejects_non_finite_or_non_positive_amounts(amount: float) -> None:
    with pytest.raises(ValidationError):
        GoalRequest(goal_amount=amount, timeframe_months=12)


@pytest.mark.parametrize("name", ["", "   "])
def test_goal_creation_requires_a_meaningful_persistent_name(name: str) -> None:
    with pytest.raises(ValidationError):
        GoalCreateRequest(goal_name=name, goal_amount=1000, timeframe_months=12)


def test_goal_create_endpoint_requires_a_goal_name_before_evaluation() -> None:
    client = TestClient(app)
    email = f"goal-schema-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    try:
        response = client.post(
            "/api/v1/goals",
            headers={"Authorization": f"Bearer {token}"},
            json={"goal_amount": 1000, "timeframe_months": 12},
        )
        assert response.status_code == 422
    finally:
        with SessionLocal() as session:
            user = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
            if user is not None:
                session.delete(user)
                session.commit()


def test_category_recommendations_use_model_1_forecasts_and_protect_essentials() -> None:
    rows: list[dict[str, object]] = []
    for month in range(1, 7):
        for category, amount in (("Shopping", 1000), ("Dining", 2000), ("Groceries", 4000), ("Rent", 10000)):
            rows.append({
                "transaction_date": f"2025-{month:02d}-10",
                "amount": amount,
                "transaction_status": "success",
                "income_flag": False,
                "transaction_class": "food" if category == "Groceries" else "expense",
                "category": category,
            })

    adjustments = GoalFeasibilityService._category_adjustments(
        rows, {"Shopping": 2000, "Dining": 3000, "Groceries": 5000, "Rent": 12000}, 1500
    )

    assert [item.category for item in adjustments] == ["Shopping", "Dining"]
    assert [item.suggested_reduction for item in adjustments] == [1000.0, 500.0]
    assert adjustments[-1].remaining_goal_savings_gap == 0
    assert all(item.suggested_reduction <= item.maximum_supported_reduction <= item.current_expected_spending for item in adjustments)
    assert all(item.spending_basis == "model_1_variable_category_forecast" for item in adjustments)


def test_negative_net_cash_is_not_reported_as_feasible() -> None:
    forecast = SimpleNamespace(
        forecast_available=True,
        expected_income=1000.0,
        expected_committed_expenses=900.0,
        expected_variable_expenses=150.0,
        expected_net_cash=-50.0,
        variable_category_forecast={},
        model_version="test-model-1",
        data_cutoff="2025-06",
    )

    class _ForecastService:
        def forecast(self, _: str):
            return forecast

    result = GoalFeasibilityService(_Dataset(), _ForecastService()).evaluate(
        "runtime-user", GoalRequest(goal_amount=300, timeframe_months=3)
    )

    assert result.required_monthly_saving == 100
    assert result.expected_monthly_saving == -50
    assert result.additional_monthly_saving_required == 150
    assert result.goal_feasible is False


def test_no_category_forecast_never_creates_a_fabricated_recommendation() -> None:
    assert GoalFeasibilityService._category_adjustments(_transactions(), {}, 1000) == []


def test_saved_goals_endpoint_loads_legacy_evaluations_after_schema_expansion() -> None:
    client = TestClient(app)
    email = f"goal-legacy-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    try:
        with SessionLocal() as session:
            account = session.query(AuthUser).filter(AuthUser.email == email).one()
            session.add(FinancialGoal(
                user_id=account.financial_user.user_id,
                goal_name="Legacy holiday",
                goal_amount=12000,
                timeframe_months=12,
                is_active=True,
                evaluation={
                    "user_id": account.financial_user.user_id,
                    "goal_amount": 12000,
                    "goal_months": 12,
                    "required_monthly_saving": 1000,
                    "expected_monthly_saving": 1500,
                    "additional_monthly_saving_required": 0,
                    "goal_feasible": True,
                    "variable_spending_adjustment_required": 0,
                    "suggested_category_adjustments": [{
                        "category": "Shopping", "current_expected_spending": 1000,
                        "suggested_reduction": 0, "adjusted_spending": 1000,
                        "reduction_percent": 0, "remaining_category_spending": 1000,
                    }],
                    "projected_variable_expenses_after_adjustment": 5000,
                    "projected_monthly_saving_after_adjustment": 1500,
                    "remaining_money_after_goal_saving": 500,
                    "explanation": "Legacy saved evaluation.",
                    "model_version": "model-2-baseline-v1",
                    "availability_status": "available",
                    "evaluation_metadata": {},
                },
            ))
            session.commit()

        response = client.get("/api/v1/goals", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["goal_name"] == "Legacy holiday"
        assert item["suggested_category_adjustments"][0]["remaining_goal_savings_gap"] is None
    finally:
        with SessionLocal() as session:
            user = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
            if user is not None:
                session.delete(user)
                session.commit()


def test_discretionary_policy_trimming_limit_caps_reduction_at_35_percent() -> None:
    # Set historical transactions where 25th percentile is higher than expected or close
    rows: list[dict[str, object]] = []
    for month in range(1, 7):
        rows.append({
            "transaction_date": f"2025-{month:02d}-15",
            "amount": 10000,
            "transaction_status": "Success",
            "income_flag": False,
            "transaction_class": "shopping",
            "category": "Shopping",
        })

    # Expected spend 8000 is lower than 25th percentile (10000), so the 35% policy limit applies
    adjustments = GoalFeasibilityService._category_adjustments(rows, {"Shopping": 8000.0}, 5000.0)

    assert len(adjustments) == 1
    adj = adjustments[0]
    assert adj.category == "Shopping"
    assert adj.current_expected_spending == 8000.0
    # 35% of 8000 is 2800
    assert adj.suggested_reduction == 2800.0
    assert adj.maximum_supported_reduction == 2800.0
    assert adj.adjusted_spending == 5200.0
    assert adj.reduction_percent == 35.0
    assert "Discretionary policy limit caps trimming at 35%" in adj.evidence


def test_essential_categories_are_strictly_protected_from_adjustments() -> None:
    rows: list[dict[str, object]] = []
    for month in range(1, 7):
        for cat in ("Groceries", "Food", "Healthcare", "Medical", "Rent", "Utilities", "Transport", "Shopping"):
            rows.append({
                "transaction_date": f"2025-{month:02d}-15",
                "amount": 5000,
                "transaction_status": "Success",
                "income_flag": False,
                "transaction_class": "expense",
                "category": cat,
            })

    forecast = {
        "Groceries": 8000.0,
        "Food": 6000.0,
        "Healthcare": 4000.0,
        "Medical": 3000.0,
        "Rent": 20000.0,
        "Utilities": 5000.0,
        "Transport": 4000.0,
        "Shopping": 7000.0,
    }

    adjustments = GoalFeasibilityService._category_adjustments(rows, forecast, 10000.0)

    categories_adjusted = [a.category for a in adjustments]
    assert categories_adjusted == ["Shopping"]
    for protected in ("Groceries", "Food", "Healthcare", "Medical", "Rent", "Utilities", "Transport"):
        assert protected not in categories_adjusted


def test_monthly_savings_plan_api_validation_and_multi_goal_persistence() -> None:
    client = TestClient(app)
    email = f"goal-plan-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    try:
        # Create Goal 1: Emergency Fund
        res1 = client.post(
            "/api/v1/goals",
            headers=headers,
            json={"goal_name": "Emergency Fund", "goal_amount": 60000, "timeframe_months": 6},
        )
        assert res1.status_code == 201
        goal1_id = res1.json()["id"]

        # Create Goal 2: Vacation
        res2 = client.post(
            "/api/v1/goals",
            headers=headers,
            json={"goal_name": "Vacation", "goal_amount": 24000, "timeframe_months": 12},
        )
        assert res2.status_code == 201
        goal2_id = res2.json()["id"]

        # Validation: Negative contribution rejected with 422
        bad_neg = client.patch(
            f"/api/v1/goals/{goal1_id}",
            headers=headers,
            json={"planned_monthly_contribution": -500},
        )
        assert bad_neg.status_code == 422

        # Validation: Contribution exceeding available capacity rejected with 422
        # (For this test user with demo transactions or zero, capacity is known or capped)
        capacity = res1.json().get("expected_monthly_saving") or 0.0
        if capacity > 0:
            bad_excess = client.patch(
                f"/api/v1/goals/{goal1_id}",
                headers=headers,
                json={"planned_monthly_contribution": capacity + 50000},
            )
            assert bad_excess.status_code == 422

            # Valid plan update on Goal 1
            planned_val = round(capacity * 0.5, 2)
            good_patch = client.patch(
                f"/api/v1/goals/{goal1_id}",
                headers=headers,
                json={"planned_monthly_contribution": planned_val},
            )
            assert good_patch.status_code == 200
            updated1 = good_patch.json()
            assert updated1["planned_monthly_contribution"] == planned_val
            assert updated1["money_remaining_after_planned_contribution"] == round(capacity - planned_val, 2)

            # Verify Goal 2 remains untouched (independent persistence)
            goal2_check = client.get(f"/api/v1/goals/{goal2_id}", headers=headers)
            assert goal2_check.status_code == 200
            assert goal2_check.json()["planned_monthly_contribution"] is None
    finally:
        with SessionLocal() as session:
            user = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
            if user is not None:
                session.delete(user)
                session.commit()


def test_saved_plan_updates_goal_feasibility_and_gap_authoritatively() -> None:
    client = TestClient(app)
    email = f"goal-authoritative-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    try:
        # Create a goal with required monthly saving of 10,000 (30,000 in 3 months)
        create_res = client.post(
            "/api/v1/goals",
            headers=headers,
            json={"goal_name": "Laptop Fund", "goal_amount": 30000, "timeframe_months": 3},
        )
        assert create_res.status_code == 201
        goal_data = create_res.json()
        goal_id = goal_data["id"]
        capacity = goal_data.get("expected_monthly_saving") or 0.0

        if capacity >= 10000:
            # 1. Update with partial contribution (e.g. 6,000 / mo)
            partial_patch = client.patch(
                f"/api/v1/goals/{goal_id}",
                headers=headers,
                json={"planned_monthly_contribution": 6000},
            )
            assert partial_patch.status_code == 200
            partial_goal = partial_patch.json()
            assert partial_goal["planned_monthly_contribution"] == 6000.0
            assert partial_goal["remaining_goal_savings_gap_after_plan"] == 4000.0
            assert "Your saved monthly contribution of ₹6,000.00 is active" in partial_goal["explanation"]

            # 2. Update with fully covering contribution (e.g. 10,000 / mo)
            full_patch = client.patch(
                f"/api/v1/goals/{goal_id}",
                headers=headers,
                json={"planned_monthly_contribution": 10000},
            )
            assert full_patch.status_code == 200
            full_goal = full_patch.json()
            assert full_goal["planned_monthly_contribution"] == 10000.0
            assert full_goal["remaining_goal_savings_gap_after_plan"] == 0.0
            assert full_goal["goal_feasible"] is True
            assert "fully covers the required monthly saving" in full_goal["explanation"]

            # 3. Reload from GET /api/v1/goals and verify exact persistence
            list_res = client.get("/api/v1/goals", headers=headers)
            assert list_res.status_code == 200
            reloaded = next(g for g in list_res.json()["items"] if g["id"] == goal_id)
            assert reloaded["planned_monthly_contribution"] == 10000.0
            assert reloaded["goal_feasible"] is True
            assert reloaded["remaining_goal_savings_gap_after_plan"] == 0.0
    finally:
        with SessionLocal() as session:
            user = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
            if user is not None:
                session.delete(user)
                session.commit()


def test_goal_deactivation_and_deletion_workflow() -> None:
    client = TestClient(app)
    email = f"goal-del-{uuid4().hex[:8]}@example.com"
    email_other = f"goal-other-{uuid4().hex[:8]}@example.com"
    password = "CorrectHorseBattery99!"

    res1 = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert res1.status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res_other = client.post("/api/v1/auth/register", json={"email": email_other, "password": password})
    assert res_other.status_code == 201
    token_other = client.post("/api/v1/auth/login", json={"email": email_other, "password": password}).json()["access_token"]
    headers_other = {"Authorization": f"Bearer {token_other}"}

    try:
        # Create Goal A
        g_a = client.post(
            "/api/v1/goals",
            headers=headers,
            json={"goal_name": "Laptop Fund", "goal_amount": 50000, "timeframe_months": 5},
        )
        assert g_a.status_code == 201
        id_a = g_a.json()["id"]

        # Create Goal B
        g_b = client.post(
            "/api/v1/goals",
            headers=headers,
            json={"goal_name": "Emergency Cushion", "goal_amount": 100000, "timeframe_months": 10},
        )
        assert g_b.status_code == 201
        id_b = g_b.json()["id"]

        # List should contain both
        active_list = client.get("/api/v1/goals", headers=headers).json()["items"]
        active_ids = [g["id"] for g in active_list]
        assert id_a in active_ids
        assert id_b in active_ids

        # Deactivate / delete Goal A
        del_res = client.delete(f"/api/v1/goals/{id_a}", headers=headers)
        assert del_res.status_code == 200
        del_data = del_res.json()
        assert del_data["id"] == id_a
        assert del_data["is_active"] is False

        # List should now omit Goal A and still have Goal B
        updated_list = client.get("/api/v1/goals", headers=headers).json()["items"]
        updated_ids = [g["id"] for g in updated_list]
        assert id_a not in updated_ids
        assert id_b in updated_ids

        # Cross-user tenant isolation: other user cannot delete or access Goal B
        del_other = client.delete(f"/api/v1/goals/{id_b}", headers=headers_other)
        assert del_other.status_code == 404
        get_other = client.get(f"/api/v1/goals/{id_b}", headers=headers_other)
        assert get_other.status_code == 404
    finally:
        with SessionLocal() as session:
            for em in (email, email_other):
                user = session.query(AuthUser).filter(AuthUser.email == em).one_or_none()
                if user is not None:
                    session.delete(user)
            session.commit()



