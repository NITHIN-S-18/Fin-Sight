from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.main import app

client = TestClient(app)


def authenticated_headers() -> tuple[dict[str, str], str]:
    email = f"smoke-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    ).status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, email


def remove_account(email: str) -> None:
    with SessionLocal() as session:
        account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if account is not None:
            session.delete(account)
            session.commit()


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


def test_global_dataset_routes_are_not_user_accessible():
    headers, email = authenticated_headers()
    try:
        for path in (
            "/api/v1/dataset/summary",
            "/api/v1/dataset/users",
            "/api/v1/dataset/transactions",
        ):
            assert client.get(path, headers=headers).status_code == 404
    finally:
        remove_account(email)


def test_sensitive_dataset_endpoints_require_authentication():
    for path in (
        "/api/v1/dataset/summary",
        "/api/v1/dataset/users",
        "/api/v1/dataset/transactions",
    ):
        assert client.get(path).status_code == 404


def test_valid_user_and_transactions():
    assert client.get("/api/v1/dataset/user/U001").status_code == 401
    assert client.get("/api/v1/dataset/user/U001/transactions").status_code == 401


def test_invalid_user():
    assert client.get("/api/v1/dataset/user/INVALID").status_code == 401


def test_subscriptions_emis_bnpl():
    assert client.get("/api/v1/subscriptions/U001").status_code == 401
    assert client.get("/api/v1/emis/U001").status_code == 401
    assert client.get("/api/v1/bnpl/U001").status_code == 401


def test_exposure_and_dashboard_and_ml_and_copilot():
    assert client.get("/api/v1/exposure/U001").status_code == 401
    assert client.get("/api/v1/dashboard/U001").status_code == 401
    assert client.get("/api/v1/ml/distress/U001").status_code == 401
    assert client.post(
        "/api/v1/copilot/query",
        json={"user_id": "U001", "question": "What is my exposure?"},
    ).status_code == 401
