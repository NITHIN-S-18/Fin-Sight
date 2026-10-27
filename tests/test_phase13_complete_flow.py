from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.main import app


client = TestClient(app)


def register_and_login() -> tuple[str, dict[str, str], str]:
    email = f"phase13-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert registered.status_code == 201, registered.text

    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert logged_in.status_code == 200, logged_in.text
    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}

    with SessionLocal() as session:
        user_id = session.query(AuthUser).filter(AuthUser.email == email).one().financial_user_id
    return email, headers, user_id


def upload_csv(headers: dict[str, str], merchant_prefix: str) -> None:
    content = (
        b"transaction_date,amount,merchant_name,transaction_class,frequency,recurring_flag,"
        b"income_flag,transaction_status\n"
        b"2026-01-01,100000,Salary,Income,monthly,No,Yes,success\n"
        + f"2026-01-02,499,{merchant_prefix} Streaming,Subscription,monthly,Yes,No,success\n".encode()
        + f"2026-01-03,5000,{merchant_prefix} EMI,EMI,monthly,Yes,No,success\n".encode()
        + f"2026-01-04,3000,{merchant_prefix} BNPL,BNPL,monthly,Yes,No,success\n".encode()
    )
    response = client.post(
        "/api/v1/transactions/upload",
        files={"file": ("phase13.csv", BytesIO(content), "text/csv")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["accepted_count"] == 4


def delete_account(email: str) -> None:
    with SessionLocal() as session:
        account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if account is not None:
            session.delete(account)
            session.commit()


def test_complete_two_user_backend_flow_and_isolation():
    email_a, headers_a, user_id_a = register_and_login()
    email_b, headers_b, user_id_b = register_and_login()
    try:
        me = client.get("/api/v1/auth/me", headers=headers_a)
        assert me.status_code == 200
        assert me.json()["financial_user_id"] == user_id_a

        empty_dashboard = client.get(f"/api/v1/dashboard/{user_id_a}", headers=headers_a)
        assert empty_dashboard.status_code == 200
        assert "Upload a transaction CSV" in empty_dashboard.text
        assert client.get(f"/api/v1/dataset/user/{user_id_a}/transactions", headers=headers_a).json() == []
        assert client.get(f"/api/v1/exposure/{user_id_a}", headers=headers_a).status_code == 404
        assert client.get(f"/api/v1/ml/intelligence/{user_id_a}", headers=headers_a).status_code == 404
        assert client.post(
            "/api/v1/copilot/query",
            json={"question": "What is my financial health?"},
            headers=headers_a,
        ).status_code == 404
        assert client.post(
            "/api/v1/simulator/simulate",
            json={"scenario_type": "add_subscription", "parameters": {"monthly_cost": 500}},
            headers=headers_a,
        ).status_code == 404

        upload_csv(headers_a, "Account A")
        upload_csv(headers_b, "Account B")

        assert client.get("/api/v1/transactions/imports", headers=headers_a).json()[0]["file_name"] == "phase13.csv"
        transactions_a = client.get(
            f"/api/v1/dataset/user/{user_id_a}/transactions",
            headers=headers_a,
        )
        transactions_b = client.get(
            f"/api/v1/dataset/user/{user_id_b}/transactions",
            headers=headers_b,
        )
        assert transactions_a.status_code == 200
        assert transactions_b.status_code == 200
        assert "Account A" in transactions_a.text
        assert "Account B" not in transactions_a.text
        assert "Account B" in transactions_b.text
        assert "Account A" not in transactions_b.text

        for user_id, headers, merchant in (
            (user_id_a, headers_a, "Account A"),
            (user_id_b, headers_b, "Account B"),
        ):
            dashboard = client.get(f"/api/v1/dashboard/{user_id}", headers=headers)
            subscriptions = client.get(f"/api/v1/subscriptions/{user_id}", headers=headers)
            emis = client.get(f"/api/v1/emis/{user_id}", headers=headers)
            bnpl = client.get(f"/api/v1/bnpl/{user_id}", headers=headers)
            exposure = client.get(f"/api/v1/exposure/{user_id}", headers=headers)
            ml = client.get(f"/api/v1/ml/intelligence/{user_id}", headers=headers)
            copilot = client.post(
                "/api/v1/copilot/query",
                json={"question": "What is my financial health?"},
                headers=headers,
            )
            what_if = client.post(
                "/api/v1/simulator/simulate",
                json={"scenario_type": "add_subscription", "parameters": {"monthly_cost": 500}},
                headers=headers,
            )

            assert dashboard.status_code == 200
            assert subscriptions.status_code == 200
            assert emis.status_code == 200
            assert bnpl.status_code == 200
            assert exposure.status_code == 200
            assert "financial_health" in exposure.json()
            assert ml.status_code == 200
            assert copilot.status_code == 200
            assert what_if.status_code == 200
            assert merchant in dashboard.text
            assert merchant in subscriptions.text
            assert merchant in emis.text
            assert merchant in bnpl.text
            assert merchant not in (
                (client.get(f"/api/v1/dashboard/{user_id_b if user_id == user_id_a else user_id_a}", headers=headers_a if user_id == user_id_a else headers_b)).text
            )

        cross_account_paths = (
            f"/api/v1/dashboard/{user_id_b}",
            f"/api/v1/dataset/user/{user_id_b}/transactions",
            f"/api/v1/subscriptions/{user_id_b}",
            f"/api/v1/emis/{user_id_b}",
            f"/api/v1/bnpl/{user_id_b}",
            f"/api/v1/exposure/{user_id_b}",
            f"/api/v1/ml/intelligence/{user_id_b}",
            f"/api/v1/copilot/suggestions/{user_id_b}",
        )
        for path in cross_account_paths:
            assert client.get(path, headers=headers_a).status_code == 403
    finally:
        delete_account(email_a)
        delete_account(email_b)
