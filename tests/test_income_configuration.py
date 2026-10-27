from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.database.models.user import User
from app.database.models.user_income_configuration import UserIncomeConfiguration
from app.main import app


def create_test_account(client: TestClient) -> tuple[str, str, dict[str, str]]:
    email = f"income-test-{uuid4().hex[:8]}@example.com"
    password = "correct-horse-battery-123"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Income Tester"},
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()
    financial_user_id = auth_data["financial_user_id"]

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return email, financial_user_id, {"Authorization": f"Bearer {token}"}


def cleanup_account(email: str) -> None:
    with SessionLocal() as session:
        user = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if user is not None:
            session.delete(user)
            session.commit()


def test_income_config_requires_authentication() -> None:
    client = TestClient(app)
    unauth_get = client.get("/api/v1/income/config")
    assert unauth_get.status_code == 401

    unauth_put = client.put("/api/v1/income/config", json={"income_mode": "manual", "manual_monthly_income": 50000})
    assert unauth_put.status_code == 401


def test_income_config_default_auto_mode() -> None:
    client = TestClient(app)
    email, user_id, headers = create_test_account(client)
    try:
        res = client.get("/api/v1/income/config", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == user_id
        assert data["income_mode"] == "auto"
        assert data["manual_monthly_income"] is None
        assert data["expected_monthly_income"] is None
        assert data["income_source_label"] in ("Observed", "Estimated")
    finally:
        cleanup_account(email)


def test_manual_income_configuration_flow_and_recalculation() -> None:
    client = TestClient(app)
    email, user_id, headers = create_test_account(client)
    try:
        # 1. Add a recurring payment of 15,000 to have known commitments
        rp_payload = {
            "name": "Car Loan EMI",
            "category": "EMI",
            "amount": 15000,
            "frequency": "Monthly",
            "next_expected_date": (date.today() + timedelta(days=10)).isoformat(),
        }
        rp_res = client.post("/api/v1/recurring-payments", headers=headers, json=rp_payload)
        assert rp_res.status_code == 201

        # 2. Set manual income to 75,000
        income_payload = {
            "income_mode": "manual",
            "manual_monthly_income": 75000.0,
            "effective_date": "2026-01-01",
        }
        put_res = client.put("/api/v1/income/config", headers=headers, json=income_payload)
        assert put_res.status_code == 200
        config_data = put_res.json()
        assert config_data["income_mode"] == "manual"
        assert config_data["manual_monthly_income"] == 75000.0
        assert config_data["effective_monthly_income"] == 75000.0
        assert config_data["income_source_label"] == "Manual"

        # 3. Check exposure intelligence incorporates manual income
        exp_res = client.get(f"/api/v1/exposure/{user_id}", headers=headers)
        assert exp_res.status_code == 200
        exp_data = exp_res.json()
        status = exp_data["current_financial_status"]
        assert status["monthly_financial_capacity"] == 75000.0
        assert status["income_source"] == "Manual"
        assert status["income_mode"] == "manual"
        assert status["monthly_total_commitments"] == 15000.0
        # exposure_score = (15000 / 75000) * 100 = 20.0
        assert status["exposure_score"] == 20.0
        # available_capacity = 75000 - 15000 = 60000.0
        assert status["available_monthly_capacity"] == 60000.0

        # Upload a transaction CSV to unlock full dashboard
        csv_bytes = b"transaction_date,amount,merchant_name,category,transaction_class\n2026-06-01,15000.00,HDFC Bank,EMI,EMI\n"
        upload_res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("test.csv", BytesIO(csv_bytes), "text/csv")},
            headers=headers,
        )
        assert upload_res.status_code == 201

        # 4. Check dashboard reflects the manual income and source label
        dash_res = client.get(f"/api/v1/dashboard/{user_id}", headers=headers)
        assert dash_res.status_code == 200
        dash_data = dash_res.json()
        exp_card = dash_data["exposure_card"]
        assert exp_card["monthly_financial_capacity"] == 75000.0
        assert exp_card["income_source"] == "Manual"
        assert exp_card["income_mode"] == "manual"
        assert exp_card["exposure_score"] == 20.0
        assert exp_card["available_monthly_capacity"] == 60000.0

        # 5. Switch back to auto mode
        auto_payload = {"income_mode": "auto"}
        auto_res = client.put("/api/v1/income/config", headers=headers, json=auto_payload)
        assert auto_res.status_code == 200
        auto_data = auto_res.json()
        assert auto_data["income_mode"] == "auto"
        assert auto_data["income_source_label"] in ("Observed", "Estimated")

        # 6. Verify exposure returned to non-manual source
        exp_after_auto = client.get(f"/api/v1/exposure/{user_id}", headers=headers).json()
        assert exp_after_auto["current_financial_status"]["income_source"] in ("Observed", "Estimated")
        assert exp_after_auto["current_financial_status"]["income_mode"] == "auto"
    finally:
        cleanup_account(email)


def test_expected_future_income_mode() -> None:
    client = TestClient(app)
    email, user_id, headers = create_test_account(client)
    try:
        # Set expected future income to 120,000 for planning
        payload = {
            "income_mode": "expected",
            "expected_monthly_income": 120000.0,
        }
        put_res = client.put("/api/v1/income/config", headers=headers, json=payload)
        assert put_res.status_code == 200
        config = put_res.json()
        assert config["income_mode"] == "expected"
        assert config["expected_monthly_income"] == 120000.0
        # Expected income must NOT replace live current capacity
        assert config["income_source_label"] in ("Observed", "Estimated")
        assert config["effective_monthly_income"] != 120000.0 or config["auto_detected_income"] == 120000.0

        # Verify exposure status carries expected_monthly_income metadata for simulators
        exp_res = client.get(f"/api/v1/exposure/{user_id}", headers=headers)
        assert exp_res.status_code == 200
        status = exp_res.json()["current_financial_status"]
        assert status["expected_monthly_income"] == 120000.0
        assert status["income_mode"] == "expected"
    finally:
        cleanup_account(email)


def test_income_validation_rules() -> None:
    client = TestClient(app)
    email, user_id, headers = create_test_account(client)
    try:
        # Negative income
        res_neg = client.put(
            "/api/v1/income/config",
            headers=headers,
            json={"income_mode": "manual", "manual_monthly_income": -500},
        )
        assert res_neg.status_code == 422

        # Zero manual income in manual mode
        res_zero = client.put(
            "/api/v1/income/config",
            headers=headers,
            json={"income_mode": "manual", "manual_monthly_income": 0},
        )
        assert res_zero.status_code == 422

        # Missing manual income in manual mode
        res_missing = client.put(
            "/api/v1/income/config",
            headers=headers,
            json={"income_mode": "manual"},
        )
        assert res_missing.status_code == 422

        # Excessive unrealistic amount (> 1 billion)
        res_excess = client.put(
            "/api/v1/income/config",
            headers=headers,
            json={"income_mode": "manual", "manual_monthly_income": 2_000_000_000},
        )
        assert res_excess.status_code == 422

        # Negative expected income
        res_neg_exp = client.put(
            "/api/v1/income/config",
            headers=headers,
            json={"income_mode": "expected", "expected_monthly_income": -100},
        )
        assert res_neg_exp.status_code == 422
    finally:
        cleanup_account(email)


def test_income_tenant_isolation() -> None:
    client = TestClient(app)
    email1, user_id1, headers1 = create_test_account(client)
    email2, user_id2, headers2 = create_test_account(client)
    try:
        # User 1 sets manual income to 90,000
        client.put(
            "/api/v1/income/config",
            headers=headers1,
            json={"income_mode": "manual", "manual_monthly_income": 90000.0},
        )

        # User 2 sets manual income to 45,000
        client.put(
            "/api/v1/income/config",
            headers=headers2,
            json={"income_mode": "manual", "manual_monthly_income": 45000.0},
        )

        # Check User 1 config
        res1 = client.get("/api/v1/income/config", headers=headers1).json()
        assert res1["manual_monthly_income"] == 90000.0
        assert res1["effective_monthly_income"] == 90000.0

        # Check User 2 config
        res2 = client.get("/api/v1/income/config", headers=headers2).json()
        assert res2["manual_monthly_income"] == 45000.0
        assert res2["effective_monthly_income"] == 45000.0

        # Check exposure isolation
        exp1 = client.get(f"/api/v1/exposure/{user_id1}", headers=headers1).json()
        assert exp1["current_financial_status"]["monthly_financial_capacity"] == 90000.0

        exp2 = client.get(f"/api/v1/exposure/{user_id2}", headers=headers2).json()
        assert exp2["current_financial_status"]["monthly_financial_capacity"] == 45000.0
    finally:
        cleanup_account(email1)
        cleanup_account(email2)
