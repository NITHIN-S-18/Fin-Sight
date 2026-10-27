from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.main import app


client = TestClient(app)


def _account() -> tuple[str, dict[str, str], str]:
    email = f"post-regression-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    with SessionLocal() as session:
        user_id = session.query(AuthUser).filter(AuthUser.email == email).one().financial_user_id
    return email, {"Authorization": f"Bearer {token}"}, user_id


def _upload(headers: dict[str, str]) -> None:
    rows = [
        "transaction_date,amount,merchant_name,transaction_class,category,transaction_status",
        "2026-01-01,85000,ACME Technologies,Income,Income,success",
        "2026-02-01,85000,ACME Technologies,Income,Income,success",
        "2026-03-01,85000,ACME Technologies,Income,Income,success",
        "2026-01-05,999,StreamCo,Subscription,Subscription,success",
        "2026-02-05,999,StreamCo,Subscription,Subscription,success",
        "2026-03-05,999,StreamCo,Subscription,Subscription,success",
    ]
    response = client.post(
        "/api/v1/transactions/upload",
        files={"file": ("post-regression.csv", BytesIO(("\n".join(rows) + "\n").encode()), "text/csv")},
        headers=headers,
    )
    assert response.status_code == 201, response.text


def _delete(email: str) -> None:
    with SessionLocal() as session:
        account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if account is not None:
            session.delete(account)
            session.commit()


def test_authenticated_commitment_surfaces_share_canonical_values() -> None:
    email, headers, user_id = _account()
    try:
        _upload(headers)
        recurring = client.get("/api/v1/recurring-payments", headers=headers)
        snapshot = client.get("/api/v1/commitments", headers=headers)
        exposure = client.get(f"/api/v1/exposure/{user_id}", headers=headers)

        assert recurring.status_code == 200
        assert snapshot.status_code == 200
        assert exposure.status_code == 200

        recurring_items = recurring.json()["items"]
        assert all(item["category"].lower() != "income" for item in recurring_items)
        canonical = snapshot.json()
        current = exposure.json()["current_financial_status"]
        assert canonical["total_monthly_commitments"] == current["monthly_total_commitments"]
        assert current["monthly_subscription_commitment"] == canonical["breakdown_by_category"].get("subscription", 0.0)

        # Dashboard quick_statistics must match the exact canonical commitments total
        dash = client.get(f"/api/v1/dashboard/{user_id}", headers=headers)
        assert dash.status_code == 200
        dash_data = dash.json()
        assert dash_data["quick_statistics"]["monthly_commitments_total"] == canonical["total_monthly_commitments"]
        assert dash_data["exposure_card"]["monthly_total_commitments"] == canonical["total_monthly_commitments"]

        # Cashflow forecast must align expected committed expenses with canonical commitments
        fc = client.get(f"/api/v1/forecast/{user_id}", headers=headers)
        if fc.status_code == 200 and fc.json()["forecast_available"]:
            assert fc.json()["expected_committed_expenses"] == canonical["total_monthly_commitments"]
    finally:
        _delete(email)


def test_manual_income_propagation_to_forecast_and_dashboard() -> None:
    email, headers, user_id = _account()
    try:
        _upload(headers)
        # Configure manual income to 95,000
        put_res = client.put(
            "/api/v1/income/config",
            headers=headers,
            json={"income_mode": "manual", "manual_monthly_income": 95000.0},
        )
        assert put_res.status_code == 200

        # Verify Exposure reflects manual income
        exp = client.get(f"/api/v1/exposure/{user_id}", headers=headers).json()
        status = exp["current_financial_status"]
        assert status["monthly_financial_capacity"] == 95000.0
        assert status["income_source"] == "Manual"
        assert status["income_mode"] == "manual"

        # Verify Dashboard reflects manual income
        dash = client.get(f"/api/v1/dashboard/{user_id}", headers=headers).json()
        assert dash["exposure_card"]["monthly_financial_capacity"] == 95000.0
        assert dash["exposure_card"]["income_source"] == "Manual"

        # Verify Forecast reflects manual income for prospective planning
        fc = client.get(f"/api/v1/forecast/{user_id}", headers=headers)
        if fc.status_code == 200 and fc.json()["forecast_available"]:
            assert fc.json()["expected_income"] == 95000.0
    finally:
        _delete(email)


def test_shortfall_predictive_consistency_with_positive_cashflow() -> None:
    email, headers, user_id = _account()
    # 7 months of healthy cashflow
    rows = ["transaction_date,amount,merchant_name,transaction_class,category,transaction_status"]
    for m in range(1, 8):
        date = f"2025-{m:02d}-10"
        rows.append(f"{date},80000,Employer Transfer,Income,Income,success")
        rows.append(f"{date},5000,Airtel Broadband,Subscription,Subscription,success")
        rows.append(f"{date},10000,Grocery Store,Other,Food,success")
    try:
        client.post(
            "/api/v1/transactions/upload",
            files={"file": ("healthy.csv", BytesIO(("\n".join(rows) + "\n").encode()), "text/csv")},
            headers=headers,
        )
        sf_res = client.get(f"/api/v1/ml/shortfall/{user_id}", headers=headers)
        assert sf_res.status_code == 200
        sf_data = sf_res.json()
        assert sf_data["available"] is True
        # Strong surplus (~65,000 net cash / month) must NOT produce high risk
        assert sf_data["shortfall_risk"] in ("LOW", "MODERATE")
        assert sf_data["prediction"] == "UNLIKELY_SHORTFALL"
        assert "historical net cash deficits" not in sf_data["risk_explanation"]
    finally:
        _delete(email)

