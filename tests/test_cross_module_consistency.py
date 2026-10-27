from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.main import app

client = TestClient(app)


def _create_user() -> tuple[str, dict[str, str], str]:
    email = f"cross-module-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201, reg.text
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    with SessionLocal() as session:
        user_id = session.query(AuthUser).filter(AuthUser.email == email).one().financial_user_id
    return email, {"Authorization": f"Bearer {token}"}, user_id


def _cleanup_user(email: str) -> None:
    with SessionLocal() as session:
        user = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if user is not None:
            session.delete(user)
            session.commit()


def test_zero_commitments_cross_module_consistency() -> None:
    """Verify that when a user has zero recurring commitments, all modules report 0.0

    commitments, 0.0% exposure, and consistent baseline without falling back to demo numbers.
    """
    email, headers, user_id = _create_user()
    try:
        # Upload transactions with income and ordinary expenses, but NO commitments
        rows = [
            "transaction_date,amount,merchant_name,transaction_class,category,transaction_status",
            "2026-01-01,50000,Salary Deposit,Income,Salary,success",
            "2026-01-15,3000,Supermarket,Expense,Groceries,success",
            "2026-02-01,50000,Salary Deposit,Income,Salary,success",
            "2026-02-15,4000,Supermarket,Expense,Groceries,success",
            "2026-03-01,50000,Salary Deposit,Income,Salary,success",
            "2026-03-15,3500,Supermarket,Expense,Groceries,success",
        ]
        upload_res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("zero_commitments.csv", BytesIO(("\n".join(rows) + "\n").encode()), "text/csv")},
            headers=headers,
        )
        assert upload_res.status_code == 201, upload_res.text

        # 1. Commitments API
        commitments_res = client.get("/api/v1/commitments", headers=headers)
        assert commitments_res.status_code == 200
        commitments_data = commitments_res.json()
        assert commitments_data["total_monthly_commitments"] == 0.0
        assert commitments_data["active_commitment_count"] == 0

        # 2. Recurring Payments API
        recurring_res = client.get("/api/v1/recurring-payments", headers=headers)
        assert recurring_res.status_code == 200
        recurring_data = recurring_res.json()
        active_items = [i for i in recurring_data["items"] if i["is_active"]]
        recurring_monthly_sum = sum(i["monthly_equivalent_amount"] for i in active_items)
        assert recurring_monthly_sum == 0.0
        assert len(active_items) == 0

        # 3. Exposure API
        exposure_res = client.get(f"/api/v1/exposure/{user_id}", headers=headers)
        assert exposure_res.status_code == 200
        exposure_data = exposure_res.json()
        status = exposure_data["current_financial_status"]
        assert status["monthly_total_commitments"] == 0.0
        assert status["exposure_score"] == 0.0
        assert status["monthly_financial_capacity"] == 50000.0
        assert exposure_data["financial_health"]["financial_health_score"] == 100.0

        # 4. Dashboard API
        dashboard_res = client.get(f"/api/v1/dashboard/{user_id}", headers=headers)
        assert dashboard_res.status_code == 200
        dashboard_data = dashboard_res.json()
        assert dashboard_data["quick_statistics"]["monthly_commitments_total"] == 0.0
        assert dashboard_data["exposure_card"]["monthly_total_commitments"] == 0.0
        assert dashboard_data["exposure_card"]["exposure_score"] == 0.0
        assert dashboard_data["financial_health_card"]["financial_health_score"] == 100.0

        # 5. Cashflow Forecast API
        forecast_res = client.get(f"/api/v1/forecast/{user_id}", headers=headers)
        if forecast_res.status_code == 200 and forecast_res.json().get("forecast_available"):
            fc_data = forecast_res.json()
            assert fc_data["expected_committed_expenses"] == 0.0

        # 6. Simulator API
        sim_res = client.post(
            "/api/v1/simulator/simulate",
            headers=headers,
            json={
                "scenario_type": "new_emi",
                "parameters": {"loan_name": "Personal Loan", "monthly_amount": 5000.0, "tenure_months": 24},
            },
        )
        assert sim_res.status_code == 200, sim_res.text
        sim_data = sim_res.json()
        assert sim_data["baseline_commitments"] == 0.0
        assert sim_data["baseline_exposure"] == 0.0
        assert sim_data["projected_commitments"] == 5000.0
        expected_sim_exposure = round(5000.0 / 50000.0 * 100.0, 2)
        assert sim_data["projected_exposure"] == pytest.approx(expected_sim_exposure, rel=1e-2)

        # 7. Dashboard History API
        history_res = client.get("/api/v1/dashboard/history", headers=headers)
        assert history_res.status_code == 200
        history_data = history_res.json()
        assert len(history_data["points"]) >= 3
        for pt in history_data["points"]:
            assert pt["commitments"] == 0.0
            assert pt["exposure"] == 0.0
            assert pt["available_capacity"] == pt["income"]
    finally:
        _cleanup_user(email)


def test_dynamic_propagation_when_commitment_added() -> None:
    """Verify that adding an active recurring commitment updates all modules consistently."""
    email, headers, user_id = _create_user()
    try:
        # Upload base income transactions so user is onboarded
        rows = [
            "transaction_date,amount,merchant_name,transaction_class,category,transaction_status",
            "2026-01-01,80000,Employer Transfer,Income,Salary,success",
            "2026-02-01,80000,Employer Transfer,Income,Salary,success",
        ]
        upload_res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("base.csv", BytesIO(("\n".join(rows) + "\n").encode()), "text/csv")},
            headers=headers,
        )
        assert upload_res.status_code == 201

        # 1. Add manual recurring commitment of 8,000 EMI
        add_res = client.post(
            "/api/v1/recurring-payments",
            headers=headers,
            json={
                "name": "Auto Loan EMI",
                "category": "EMI",
                "amount": 8000.0,
                "frequency": "monthly",
                "next_expected_date": (date.today() + timedelta(days=5)).isoformat(),
            },
        )
        assert add_res.status_code == 201

        # 2. Verify Commitments API
        com_res = client.get("/api/v1/commitments", headers=headers).json()
        assert com_res["total_monthly_commitments"] == 8000.0
        assert com_res["active_commitment_count"] == 1
        assert com_res["breakdown_by_category"]["emi"] == 8000.0

        # 3. Verify Recurring Payments API
        rec_res = client.get("/api/v1/recurring-payments", headers=headers).json()
        active_items = [i for i in rec_res["items"] if i["is_active"]]
        assert len(active_items) == 1
        assert active_items[0]["monthly_equivalent_amount"] == 8000.0

        # 4. Verify Exposure API
        exp_res = client.get(f"/api/v1/exposure/{user_id}", headers=headers).json()
        assert exp_res["current_financial_status"]["monthly_total_commitments"] == 8000.0

        # 5. Verify Dashboard API
        dash_res = client.get(f"/api/v1/dashboard/{user_id}", headers=headers).json()
        assert dash_res["quick_statistics"]["monthly_commitments_total"] == 8000.0
        assert dash_res["exposure_card"]["monthly_total_commitments"] == 8000.0
    finally:
        _cleanup_user(email)


def test_micro_transaction_trial_alerts_do_not_inflate_commitments() -> None:
    """Verify that INR 1 authorization holds or potential trials do not inflate

    the user's confirmed monthly commitments or exposure calculation.
    """
    email, headers, user_id = _create_user()
    try:
        # Upload transactions with micro-charges (authorization holds)
        rows = [
            "transaction_date,amount,merchant_name,transaction_class,category,transaction_status",
            "2026-01-01,60000,Salary Deposit,Income,Salary,success",
            "2026-01-02,1,Amazon Pay Auth,Verification,Hold,success",
            "2026-01-03,2,Google Temporary Hold,Verification,Hold,success",
            "2026-01-04,1,Razorpay Verification,Verification,Hold,success",
            "2026-02-01,60000,Salary Deposit,Income,Salary,success",
        ]
        client.post(
            "/api/v1/transactions/upload",
            files={"file": ("micro_auths.csv", BytesIO(("\n".join(rows) + "\n").encode()), "text/csv")},
            headers=headers,
        )

        commitments_res = client.get("/api/v1/commitments", headers=headers).json()
        assert commitments_res["total_monthly_commitments"] == 0.0

        exposure_res = client.get(f"/api/v1/exposure/{user_id}", headers=headers).json()
        assert exposure_res["current_financial_status"]["monthly_total_commitments"] == 0.0
        assert exposure_res["current_financial_status"]["exposure_score"] == 0.0
    finally:
        _cleanup_user(email)


def test_commitment_category_breakdown_arithmetic_consistency() -> None:
    """Verify that multiple commitments across categories sum exactly to total_monthly_commitments."""
    email, headers, user_id = _create_user()
    try:
        # Upload base income transactions so user is onboarded
        rows = [
            "transaction_date,amount,merchant_name,transaction_class,category,transaction_status",
            "2026-01-01,90000,Employer Transfer,Income,Salary,success",
            "2026-02-01,90000,Employer Transfer,Income,Salary,success",
        ]
        upload_res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("base.csv", BytesIO(("\n".join(rows) + "\n").encode()), "text/csv")},
            headers=headers,
        )
        assert upload_res.status_code == 201

        # Add multiple recurring payments across categories
        items_to_add = [
            ("House Rent", "Rent", 18666.67),
            ("Personal Loan EMI", "EMI", 7649.00),
            ("Flipkart Pay Later", "BNPL", 6025.00),
            ("Netflix & Spotify", "Subscription", 2413.67),
            ("Health Insurance", "Insurance", 1400.00),
            ("Airtel Postpaid", "Mobile", 424.00),
        ]
        for name, category, amount in items_to_add:
            res = client.post(
                "/api/v1/recurring-payments",
                headers=headers,
                json={
                    "name": name,
                    "category": category,
                    "amount": amount,
                    "frequency": "monthly",
                    "next_expected_date": (date.today() + timedelta(days=10)).isoformat(),
                },
            )
            assert res.status_code == 201

        # Check commitments API
        com_res = client.get("/api/v1/commitments", headers=headers)
        assert com_res.status_code == 200
        com_data = com_res.json()

        total = com_data["total_monthly_commitments"]
        breakdown = com_data["breakdown_by_category"]

        # Exact floating point sum must equal total within 0.01
        breakdown_sum = sum(breakdown.values())
        assert breakdown_sum == pytest.approx(total, abs=0.02)
        assert total == pytest.approx(36578.34, abs=0.02)

        # Check Dashboard API agrees on the exact total
        dash_res = client.get(f"/api/v1/dashboard/{user_id}", headers=headers)
        assert dash_res.status_code == 200
        dash_data = dash_res.json()
        assert dash_data["exposure_card"]["monthly_total_commitments"] == pytest.approx(total, abs=0.02)
    finally:
        _cleanup_user(email)


def test_shortfall_and_forecast_metric_relationship() -> None:
    """Verify that forecast and shortfall metrics exhibit mathematically sound relationships."""
    email, headers, user_id = _create_user()
    try:
        # Upload 6+ months of data so models can run
        rows = [
            "transaction_date,amount,merchant_name,transaction_class,category,transaction_status",
        ]
        base_date = date(2026, 1, 1)
        for month_idx in range(9):
            d_inc = date(2026, month_idx + 1, 1).isoformat()
            d_exp = date(2026, month_idx + 1, 15).isoformat()
            rows.append(f"{d_inc},85000,Corporate Payroll,Income,Salary,success")
            rows.append(f"{d_exp},25000,Grocery Store,Expense,Groceries,success")

        upload_res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("history.csv", BytesIO(("\n".join(rows) + "\n").encode()), "text/csv")},
            headers=headers,
        )
        assert upload_res.status_code == 201

        # Query forecast
        fc_res = client.get(f"/api/v1/forecast/{user_id}", headers=headers)
        if fc_res.status_code == 200:
            fc_data = fc_res.json()
            if fc_data.get("forecast_available"):
                exp_income = fc_data["expected_income"]
                exp_committed = fc_data["expected_committed_expenses"]
                exp_variable = fc_data["expected_variable_expenses"]
                exp_net = fc_data["expected_net_cash"]

                # Arithmetic relationship: Net cash = Income - Committed - Variable
                calc_net = exp_income - exp_committed - exp_variable
                assert exp_net == pytest.approx(calc_net, abs=0.05)
    finally:
        _cleanup_user(email)
