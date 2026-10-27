from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.main import app


def account(client: TestClient) -> tuple[str, dict[str, str]]:
    email = f"commitment-phase4-{uuid4().hex}@example.com"
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


def test_unified_snapshot_includes_active_manual_and_excludes_deactivated() -> None:
    client = TestClient(app)
    email, headers = account(client)
    try:
        created = client.post(
            "/api/v1/recurring-payments",
            headers=headers,
            json={
                "name": "House Rent",
                "category": "Rent",
                "amount": 20000,
                "frequency": "monthly",
                "next_expected_date": (date.today() + timedelta(days=10)).isoformat(),
            },
        )
        assert created.status_code == 201
        recurring_id = created.json()["id"]

        snapshot = client.get("/api/v1/commitments", headers=headers)
        assert snapshot.status_code == 200
        assert snapshot.json()["total_monthly_commitments"] == 20000
        assert snapshot.json()["user_added_commitment_count"] == 1
        assert snapshot.json()["breakdown_by_category"]["rent"] == 20000

        removed = client.delete(f"/api/v1/recurring-payments/{recurring_id}", headers=headers)
        assert removed.status_code == 200
        assert client.get("/api/v1/commitments", headers=headers).json()["total_monthly_commitments"] == 0
    finally:
        cleanup(email)


def test_unified_snapshot_is_tenant_scoped() -> None:
    client = TestClient(app)
    owner_email, owner_headers = account(client)
    other_email, other_headers = account(client)
    try:
        created = client.post(
            "/api/v1/recurring-payments",
            headers=owner_headers,
            json={
                "name": "Private Insurance",
                "category": "Insurance",
                "amount": 5000,
                "frequency": "monthly",
                "next_expected_date": (date.today() + timedelta(days=10)).isoformat(),
            },
        )
        assert created.status_code == 201
        assert client.get("/api/v1/commitments", headers=other_headers).json()["total_monthly_commitments"] == 0
    finally:
        cleanup(owner_email)
        cleanup(other_email)
