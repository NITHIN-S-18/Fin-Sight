from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.database.models.trial_intelligence import TrialIntelligence
from app.main import app


def account(client: TestClient) -> tuple[str, dict[str, str]]:
    email = f"trial-phase3-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return email, {"Authorization": f"Bearer {token}"}


def cleanup(email: str) -> None:
    with SessionLocal() as session:
        user = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if user is not None:
            session.delete(user)
            session.commit()


def upload(client: TestClient, headers: dict[str, str], csv: str):
    return client.post(
        "/api/v1/transactions/upload",
        headers=headers,
        files={"file": ("trial.csv", csv.encode(), "text/csv")},
    )


def test_authorization_hold_does_not_claim_trial_and_duplicate_upload_is_suppressed():
    client = TestClient(app)
    email, headers = account(client)
    try:
        csv = (
            "transaction_date,amount,merchant_name,description,transaction_status\n"
            "2026-09-01T10:00:00,2,Netflix,card verification,success\n"
        )
        assert upload(client, headers, csv).status_code == 201
        assert upload(client, headers, csv).status_code == 201
        response = client.get("/api/v1/trial-intelligence", headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["detected_state"] == "possible_trial"
        assert response.json()["items"][0]["possible_conversion_date"] is None
    finally:
        cleanup(email)


def test_explicit_trial_duration_produces_conversion_date_without_generic_fallback():
    client = TestClient(app)
    email, headers = account(client)
    try:
        csv = (
            "transaction_date,amount,merchant_name,description,transaction_status\n"
            "2026-10-01T10:00:00,1,Acme Video,free trial 7 days authorization,success\n"
        )
        assert upload(client, headers, csv).status_code == 201
        item = client.get("/api/v1/trial-intelligence", headers=headers).json()["items"][0]
        assert item["detected_state"] == "possible_conversion"
        assert item["possible_conversion_date"] == "2026-10-08"
    finally:
        cleanup(email)


def test_negative_microtransaction_is_ignored_and_tenant_isolation_holds():
    client = TestClient(app)
    owner_email, owner_headers = account(client)
    other_email, other_headers = account(client)
    try:
        csv = (
            "transaction_date,amount,merchant_name,description,transaction_status\n"
            "2026-09-01T10:00:00,-2,Netflix,authorization refund,success\n"
        )
        assert upload(client, owner_headers, csv).status_code == 201
        assert client.get("/api/v1/trial-intelligence", headers=owner_headers).json()["total"] == 0
        assert client.get("/api/v1/trial-intelligence", headers=other_headers).json()["total"] == 0
    finally:
        cleanup(owner_email)
        cleanup(other_email)
