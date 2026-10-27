from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.main import app


client = TestClient(app)


def _account():
    email = f"shortfall-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    with SessionLocal() as session:
        user_id = session.query(AuthUser).filter(AuthUser.email == email).one().financial_user_id
    return email, {"Authorization": f"Bearer {token}"}, user_id


def _remove(*emails: str):
    with SessionLocal() as session:
        for email in emails:
            account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
            if account is not None:
                session.delete(account)
        session.commit()


def test_shortfall_endpoint_auth_tenant_isolation_and_insufficient_history():
    email_a, headers_a, user_a = _account()
    email_b, headers_b, user_b = _account()
    try:
        own = client.get(f"/api/v1/ml/shortfall/{user_a}", headers=headers_a)
        assert own.status_code == 200
        assert own.json()["available"] is False
        assert own.json()["availability_status"] == "insufficient_history"
        assert client.get(f"/api/v1/ml/shortfall/{user_b}", headers=headers_a).status_code == 403
        assert client.get(f"/api/v1/ml/shortfall/{user_a}", headers=headers_b).status_code == 403
        assert client.get(f"/api/v1/ml/shortfall/{user_a}").status_code == 401
    finally:
        _remove(email_a, email_b)


def test_shortfall_endpoint_live_inference_with_sufficient_history():
    email, headers, user_id = _account()
    rows = ["transaction_date,amount,merchant_name,category,transaction_class,income_flag,transaction_status"]
    for month in range(1, 8):
        date = f"2024-{month:02d}-15"
        rows.append(f"{date},1000,Salary,Income,Income,Yes,Success")
        rows.append(f"{date},300,Rent,Subscription,Subscription,No,Success")
        rows.append(f"{date},150,Food,Food,Other,No,Success")
    try:
        upload = client.post(
            "/api/v1/transactions/upload",
            headers=headers,
            files={"file": ("history.csv", BytesIO(("\n".join(rows) + "\n").encode()), "text/csv")},
        )
        assert upload.status_code == 201
        response = client.get(f"/api/v1/ml/shortfall/{user_id}", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["available"] is True
        assert payload["prediction"] in {"LIKELY_SHORTFALL", "UNLIKELY_SHORTFALL"}
        assert payload["shortfall_risk"] in {"LOW", "MODERATE", "HIGH"}
        assert "probability" not in payload
        # Verify factors and actions are present as lists
        assert isinstance(payload["contributing_factors"], list)
        assert isinstance(payload["recommended_actions"], list)
    finally:
        _remove(email)


def test_shortfall_empty_history_does_not_fabricate_amounts():
    email, headers, user_id = _account()
    try:
        response = client.get(f"/api/v1/ml/shortfall/{user_id}", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["available"] is False
        assert payload["availability_status"] == "insufficient_history"
        assert payload["prediction"] == "UNAVAILABLE"
        assert payload["shortfall_risk"] == "UNAVAILABLE"
        assert payload["expected_net_cash"] is None
        assert payload["expected_income"] is None
        assert payload["expected_total_expenses"] is None
    finally:
        _remove(email)


def test_shortfall_baseline_does_not_mask_negative_buffer_as_low():
    import pandas as pd
    from app.services.shortfall_service import FinancialShortfallService

    service = FinancialShortfallService()
    # Mock feature row with negative net cash buffer
    features = pd.DataFrame([{
        "net_cash_6m": -5000.0,
        "net_cash_volatility": 1000.0,
        "commitment_ratio": 0.8,
        "income_trend": -100.0,
        "variable_volatility": 500.0,
        "variable_6m": 2000.0,
        "minimum_net_cash": -6000.0,
        "variable_trend": 100.0,
        "category_growth": 50.0,
    }])
    res = service._baseline_response("TEST_USER", "2026-02", None, features)
    assert res.shortfall_risk == "HIGH"
    assert res.prediction == "LIKELY_SHORTFALL"
    assert "declining historical income trend" in res.contributing_factors
    assert "low historical cash buffer" in res.contributing_factors
    assert "recent expense increase" in res.contributing_factors


def test_shortfall_factors_and_severities_calculated_by_backend_rules():
    import pandas as pd
    from app.services.shortfall_service import FinancialShortfallService

    service = FinancialShortfallService()

    # Case A: Flat income (-3.4e-12) and insignificant variable trend (+1.0) must NOT trigger false factors
    features_flat = pd.DataFrame([{
        "net_cash_6m": -20000.0,
        "net_cash_volatility": 5000.0,
        "commitment_ratio": 0.25,
        "income_6m": 85000.0,
        "income_trend": -3.4e-12,
        "income_stability": 1.0,
        "variable_volatility": 1000.0,
        "variable_6m": 30000.0,
        "minimum_net_cash": -25000.0,
        "variable_trend": 1.0,  # insignificant (+₹1/mo)
        "commitment_growth": 0.0,
    }])
    res_flat = service._baseline_response("TEST_USER_FLAT", "2026-02", None, features_flat)
    # Income is flat -> "declining historical income trend" must be absent
    assert "declining historical income trend" not in res_flat.contributing_factors
    # Insignificant variable trend -> "recent expense increase" must be absent
    assert "recent expense increase" not in res_flat.contributing_factors
    # Negative net cash -> "low historical cash buffer" is present with HIGH severity
    assert "low historical cash buffer" in res_flat.contributing_factors
    buffer_detail = next(d for d in res_flat.factor_details if d.factor == "low historical cash buffer")
    assert buffer_detail.severity == "HIGH"

    # Case B: Significant expense increase (+₹20,000/mo) and positive Model 1 forecast
    class MockForecast:
        forecast_available = True
        expected_income = 85000.0
        expected_total_expenses = 30000.0
        expected_net_cash = 55000.0

    features_surge = pd.DataFrame([{
        "net_cash_6m": -15000.0,
        "net_cash_volatility": 2000.0,
        "commitment_ratio": 0.20,
        "income_6m": 85000.0,
        "income_trend": 0.0,
        "income_stability": 1.0,
        "variable_volatility": 5000.0,
        "variable_6m": 40000.0,
        "minimum_net_cash": -18000.0,
        "variable_trend": 20000.0,  # significant surge
        "commitment_growth": 0.0,
    }])
    res_surge = service._baseline_response("TEST_USER_SURGE", "2026-02", MockForecast(), features_surge)
    assert "recent expense increase" in res_surge.contributing_factors
    surge_detail = next(d for d in res_surge.factor_details if d.factor == "recent expense increase")
    assert surge_detail.severity == "MEDIUM"
    assert res_surge.risk_explanation is not None
    assert "positive baseline net cash" in res_surge.risk_explanation


def test_shortfall_low_risk_scenario_with_positive_buffer_and_no_adverse_factors():
    import pandas as pd
    from app.services.shortfall_service import FinancialShortfallService

    service = FinancialShortfallService()

    class HealthyForecast:
        forecast_available = True
        expected_income = 85000.0
        expected_total_expenses = 35000.0
        expected_net_cash = 50000.0

    features_healthy = pd.DataFrame([{
        "net_cash_6m": 45000.0,
        "net_cash_volatility": 1500.0,
        "commitment_ratio": 0.20,
        "income_6m": 85000.0,
        "income_trend": 500.0,
        "income_stability": 1.0,
        "variable_volatility": 1200.0,
        "variable_6m": 15000.0,
        "minimum_net_cash": 40000.0,
        "variable_trend": -200.0,
        "commitment_growth": 0.0,
    }])
    res = service._baseline_response("HEALTHY_USER", "2026-02", HealthyForecast(), features_healthy)
    assert res.shortfall_risk == "LOW"
    assert res.prediction == "UNLIKELY_SHORTFALL"
    assert "declining historical income trend" not in res.contributing_factors
    assert "low historical cash buffer" not in res.contributing_factors
    assert "recent expense increase" not in res.contributing_factors
    assert len(res.factor_details) == 1
    assert res.factor_details[0].factor == "historical cash-flow pattern is comparatively stable"
    assert res.factor_details[0].severity == "LOW"
    assert "stable cash-flow continuity" in res.risk_explanation


def test_shortfall_negative_net_cash_forecast_triggers_consistent_high_risk():
    import pandas as pd
    from app.services.shortfall_service import FinancialShortfallService

    service = FinancialShortfallService()

    class DeficitForecast:
        forecast_available = True
        expected_income = 50000.0
        expected_total_expenses = 70000.0
        expected_net_cash = -20000.0

    features_deficit = pd.DataFrame([{
        "net_cash_6m": -15000.0,
        "net_cash_volatility": 3000.0,
        "commitment_ratio": 0.50,
        "income_6m": 50000.0,
        "income_trend": -1500.0,
        "income_stability": 0.85,
        "variable_volatility": 4000.0,
        "variable_6m": 35000.0,
        "minimum_net_cash": -25000.0,
        "variable_trend": 2500.0,
        "commitment_growth": 0.1,
    }])
    res = service._baseline_response("DEFICIT_USER", "2026-02", DeficitForecast(), features_deficit)
    assert res.shortfall_risk == "HIGH"
    assert res.prediction == "LIKELY_SHORTFALL"
    assert "low historical cash buffer" in res.contributing_factors
    assert res.risk_explanation is not None
    assert "historical net cash deficits" in res.risk_explanation



