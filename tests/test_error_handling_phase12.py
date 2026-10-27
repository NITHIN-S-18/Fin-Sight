from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.copilot.copilot_service import get_copilot_service
from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.main import app


client = TestClient(app)


def create_account() -> tuple[str, dict[str, str], str]:
    email = f"error-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login.json()["access_token"]
    with SessionLocal() as session:
        user_id = session.query(AuthUser).filter(AuthUser.email == email).one().financial_user_id
    return email, {"Authorization": f"Bearer {token}"}, user_id


def delete_account(email: str) -> None:
    with SessionLocal() as session:
        account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if account is not None:
            session.delete(account)
            session.commit()


def upload_transactions(headers: dict[str, str]) -> None:
    csv = (
        b"transaction_date,amount,merchant_name,transaction_class,income_flag\n"
        b"2026-01-01,100000,Salary,Income,Yes\n"
        b"2026-01-02,799,Netflix,Subscription,No\n"
    )
    response = client.post(
        "/api/v1/transactions/upload",
        files={"file": ("transactions.csv", BytesIO(csv), "text/csv")},
        headers=headers,
    )
    assert response.status_code == 201, response.text


def test_error_status_codes_and_safe_error_shapes():
    malformed = client.post("/api/v1/auth/register", content="{not-json")
    assert malformed.status_code == 400
    assert malformed.json()["message"]

    missing_auth = client.get("/api/v1/auth/me")
    assert missing_auth.status_code == 401
    assert missing_auth.json()["message"] == "Invalid or missing authentication token"

    email, headers, user_id = create_account()
    try:
        assert client.get(f"/api/v1/dataset/user/OTHER/transactions", headers=headers).status_code == 403
        empty_exposure = client.get(f"/api/v1/exposure/{user_id}", headers=headers)
        assert empty_exposure.status_code == 404
        assert empty_exposure.json()["message"]

        duplicate = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "correct-horse-battery"},
        )
        assert duplicate.status_code == 409

        invalid_query = client.post(
            "/api/v1/copilot/query",
            json={"question": ""},
            headers=headers,
        )
        assert invalid_query.status_code == 422
        assert invalid_query.json()["details"]
    finally:
        delete_account(email)


def test_unexpected_copilot_errors_are_logged_and_sanitized():
    email, headers, _ = create_account()
    upload_transactions(headers)

    class ExplodingCopilot:
        def query_copilot(self, **_: object):
            raise RuntimeError("database password and secret token")

    app.dependency_overrides[get_copilot_service] = lambda: ExplodingCopilot()
    safe_client = TestClient(app, raise_server_exceptions=False)
    try:
        response = safe_client.post(
            "/api/v1/copilot/query",
            json={"question": "What is my financial health?"},
            headers=headers,
        )
        assert response.status_code == 500
        assert "database password" not in response.text
        assert response.json()["error"] == "internal_server_error"
    finally:
        app.dependency_overrides.pop(get_copilot_service, None)
        delete_account(email)
