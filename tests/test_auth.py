import io
import uuid
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def registered_account():
    email = f"auth-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    response = TestClient(app).post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    yield email, password, response.json()
    with SessionLocal() as session:
        user = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if user is not None:
            session.delete(user)
            session.commit()


def test_register_returns_account_without_password_hash(client: TestClient):
    email = f"register-{uuid4().hex}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery", "display_name": "Registered Name"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == email
    assert response.json()["display_name"] == "Registered Name"
    assert "password_hash" not in response.json()

    with SessionLocal() as session:
        user = session.query(AuthUser).filter(AuthUser.email == email).one()
        assert user.password_hash != "correct-horse-battery"
        assert user.display_name == "Registered Name"
        session.delete(user)
        session.commit()


def test_duplicate_registration_returns_conflict(client: TestClient, registered_account):
    email, password, _ = registered_account
    response = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert response.status_code == 409


def test_valid_login_returns_bearer_token(client: TestClient, registered_account):
    email, password, _ = registered_account
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_wrong_password_is_rejected(client: TestClient, registered_account):
    email, _, _ = registered_account
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
    assert response.status_code == 401


def test_invalid_token_is_rejected(client: TestClient):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


def test_auth_me_returns_current_user(client: TestClient, registered_account):
    email, password, _ = registered_account
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login.json()["access_token"]
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == email


def test_profile_can_be_read_and_updated_without_exposing_hash(client: TestClient, registered_account):
    email, password, _ = registered_account
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/auth/me", headers=headers).json()["display_name"] is None
    response = client.patch("/api/v1/auth/me", headers=headers, json={"display_name": "Updated Name"})
    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Name"
    assert "password_hash" not in response.json()


def test_password_change_requires_current_password_and_updates_login(client: TestClient, registered_account):
    email, password, _ = registered_account
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "wrong-password", "new_password": "new-correct-password"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": password, "new_password": "new-correct-password"},
    ).status_code == 204
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "new-correct-password"},
    ).status_code == 200


def test_password_change_invalidates_old_tokens_and_new_token_works(client: TestClient, registered_account):
    email, password, _ = registered_account
    old_token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    old_headers = {"Authorization": f"Bearer {old_token}"}

    assert client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={"current_password": password, "new_password": "new-correct-password"},
    ).status_code == 204
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401

    new_token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "new-correct-password"},
    ).json()["access_token"]
    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_token}"},
    ).status_code == 200


def test_export_requires_authentication_and_returns_csv(client: TestClient, registered_account):
    email, password, _ = registered_account
    assert client.get("/api/v1/auth/export").status_code == 401
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    response = client.get("/api/v1/auth/export", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "transaction_id" in response.text


def test_export_returns_json_when_requested(client: TestClient, registered_account):
    email, password, _ = registered_account
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    response = client.get("/api/v1/auth/export?format=json", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert "user_id" in data
    assert "transactions" in data


def test_avatar_upload_rejects_invalid_file_types(client: TestClient, registered_account):
    email, password, _ = registered_account
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    fake_file = io.BytesIO(b"not an image file content")
    response = client.post(
        "/api/v1/auth/avatar",
        headers=headers,
        files={"file": ("test.png", fake_file, "image/png")},
    )
    assert response.status_code == 422
    assert "Invalid image format" in response.text


def test_avatar_upload_and_delete_workflow(client: TestClient, registered_account):
    email, password, _ = registered_account
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    file_obj = io.BytesIO(png_bytes)
    upload_resp = client.post(
        "/api/v1/auth/avatar",
        headers=headers,
        files={"file": ("profile.png", file_obj, "image/png")},
    )
    assert upload_resp.status_code == 200
    avatar_url = upload_resp.json()["avatar_url"]
    assert avatar_url is not None
    assert "/api/v1/auth/avatar/" in avatar_url

    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["avatar_url"] == avatar_url

    filename = avatar_url.split("/api/v1/auth/avatar/")[-1]
    get_resp = client.get(f"/api/v1/auth/avatar/{filename}")
    assert get_resp.status_code == 200
    assert get_resp.headers["content-type"] == "image/png"

    del_resp = client.delete("/api/v1/auth/avatar", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["avatar_url"] is None

    assert client.get(f"/api/v1/auth/avatar/{filename}").status_code == 404


def test_financial_summary_endpoint_empty_and_scoped(client):
    suffix = uuid.uuid4().hex[:8]
    email = f"summary_{suffix}@example.com"
    password = "ValidPassword123!"

    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Authenticated summary on brand new user with 0 transactions
    resp = client.get("/api/v1/transactions/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_transactions"] == 0
    assert data["start_date"] is None
    assert data["end_date"] is None
    assert data["last_analyzed"] is None
    assert data["file_name"] is None

    # Unauthenticated request is rejected
    unauth_resp = client.get("/api/v1/transactions/summary")
    assert unauth_resp.status_code == 401


def test_user_avatar_isolation_and_persistence(client):
    suffix1 = uuid.uuid4().hex[:8]
    suffix2 = uuid.uuid4().hex[:8]
    email1 = f"user1_{suffix1}@example.com"
    email2 = f"user2_{suffix2}@example.com"
    password = "ValidPassword123!"

    client.post("/api/v1/auth/register", json={"email": email1, "password": password})
    token1 = client.post("/api/v1/auth/login", json={"email": email1, "password": password}).json()["access_token"]

    client.post("/api/v1/auth/register", json={"email": email2, "password": password})
    token2 = client.post("/api/v1/auth/login", json={"email": email2, "password": password}).json()["access_token"]

    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    file_obj = io.BytesIO(png_bytes)

    # User 1 uploads avatar
    upload_resp = client.post(
        "/api/v1/auth/avatar",
        headers={"Authorization": f"Bearer {token1}"},
        files={"file": ("user1.png", file_obj, "image/png")},
    )
    assert upload_resp.status_code == 200
    user1_avatar = upload_resp.json()["avatar_url"]

    # User 2 profile remains unaffected (None)
    user2_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token2}"}).json()
    assert user2_me["avatar_url"] is None

    # User 2 attempts to delete User 1's avatar via DELETE /api/v1/auth/avatar (scoped to caller)
    del_resp2 = client.delete("/api/v1/auth/avatar", headers={"Authorization": f"Bearer {token2}"})
    assert del_resp2.status_code == 200
    assert del_resp2.json()["avatar_url"] is None

    # User 1's avatar is still safely persisted
    user1_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token1}"}).json()
    assert user1_me["avatar_url"] == user1_avatar

