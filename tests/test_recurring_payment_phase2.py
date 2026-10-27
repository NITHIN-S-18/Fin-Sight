from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.main import app


def account(client: TestClient) -> tuple[str, dict[str, str]]:
    email = f"recurring-phase2-{uuid4().hex}@example.com"
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


def test_user_added_recurring_payment_crud_and_soft_deactivation() -> None:
    client = TestClient(app)
    email, headers = account(client)
    try:
        payload = {
            "name": "House Rent",
            "category": "Rent",
            "amount": 18000,
            "frequency": "Monthly",
            "next_expected_date": (date.today() + timedelta(days=10)).isoformat(),
        }
        created = client.post("/api/v1/recurring-payments", headers=headers, json=payload)
        assert created.status_code == 201
        item = created.json()
        assert item["source"] == "USER_ADDED"
        assert item["last_payment_date"] is None
        assert item["supporting_transaction_ids"] == []

        updated = client.patch(
            f"/api/v1/recurring-payments/{item['id']}",
            headers=headers,
            json={"amount": 20000, "frequency": "quarterly"},
        )
        assert updated.status_code == 200
        assert updated.json()["monthly_equivalent_amount"] == 6666.67

        listed = client.get("/api/v1/recurring-payments", headers=headers)
        assert listed.status_code == 200
        assert any(row["id"] == item["id"] for row in listed.json()["items"])

        removed = client.delete(f"/api/v1/recurring-payments/{item['id']}", headers=headers)
        assert removed.status_code == 200
        assert removed.json()["is_active"] is False
        assert removed.json()["status"] == "Inactive"
    finally:
        cleanup(email)


def test_recurring_payment_validation_and_tenant_isolation() -> None:
    client = TestClient(app)
    owner_email, owner_headers = account(client)
    other_email, other_headers = account(client)
    try:
        invalid = client.post(
            "/api/v1/recurring-payments",
            headers=owner_headers,
            json={
                "name": " ",
                "category": "Rent",
                "amount": 10,
                "frequency": "monthly",
                "next_expected_date": date.today().isoformat(),
            },
        )
        assert invalid.status_code == 422

        created = client.post(
            "/api/v1/recurring-payments",
            headers=owner_headers,
            json={
                "name": "Private Membership",
                "category": "membership",
                "amount": 100,
                "frequency": "monthly",
                "next_expected_date": (date.today() + timedelta(days=10)).isoformat(),
            },
        )
        recurring_id = created.json()["id"]
        assert client.get(f"/api/v1/recurring-payments/{recurring_id}", headers=other_headers).status_code == 404
        assert client.patch(
            f"/api/v1/recurring-payments/{recurring_id}",
            headers=other_headers,
            json={"amount": 1},
        ).status_code == 404
    finally:
        cleanup(owner_email)
        cleanup(other_email)


def test_batch_cancellation_simulation_and_tenant_isolation() -> None:
    client = TestClient(app)
    owner_email, owner_headers = account(client)
    other_email, other_headers = account(client)
    try:
        sub1 = client.post(
            "/api/v1/recurring-payments",
            headers=owner_headers,
            json={
                "name": "Owner Sub 1",
                "category": "subscription",
                "amount": 500,
                "frequency": "monthly",
                "next_expected_date": (date.today() + timedelta(days=10)).isoformat(),
            },
        ).json()
        sub2 = client.post(
            "/api/v1/recurring-payments",
            headers=owner_headers,
            json={
                "name": "Owner Sub 2",
                "category": "subscription",
                "amount": 1000,
                "frequency": "monthly",
                "next_expected_date": (date.today() + timedelta(days=15)).isoformat(),
            },
        ).json()

        # Batch simulation for owner
        sim_res = client.post(
            "/api/v1/recurring-payments/simulate-cancellation",
            headers=owner_headers,
            json={"recurring_payment_ids": [sub1["id"], sub2["id"]]},
        )
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        assert sim_data["selected_count"] == 2
        assert sim_data["monthly_savings"] == 1500.0
        assert sim_data["annual_potential_savings"] == 18000.0
        assert sim_data["cancellation_applied"] is False

        # Verify case-insensitive status query
        active_list = client.get("/api/v1/recurring-payments?status=active", headers=owner_headers)
        assert active_list.status_code == 200
        assert len(active_list.json()["items"]) >= 2

        # Tenant isolation: other user cannot simulate cancellation of owner's subscriptions (returns 404)
        other_sim = client.post(
            "/api/v1/recurring-payments/simulate-cancellation",
            headers=other_headers,
            json={"recurring_payment_ids": [sub1["id"], sub2["id"]]},
        )
        assert other_sim.status_code == 404
    finally:
        cleanup(owner_email)
        cleanup(other_email)


def test_batch_cancellation_simulation_empty_deduplication_and_annual_normalization() -> None:
    client = TestClient(app)
    owner_email, owner_headers = account(client)
    try:
        # Create a monthly subscription of 600
        sub_monthly = client.post(
            "/api/v1/recurring-payments",
            headers=owner_headers,
            json={
                "name": "Monthly Streaming",
                "category": "subscription",
                "amount": 600,
                "frequency": "monthly",
                "next_expected_date": (date.today() + timedelta(days=10)).isoformat(),
            },
        ).json()

        # Create an annual subscription of 1200 (100/mo)
        sub_annual = client.post(
            "/api/v1/recurring-payments",
            headers=owner_headers,
            json={
                "name": "Annual Software",
                "category": "subscription",
                "amount": 1200,
                "frequency": "annual",
                "next_expected_date": (date.today() + timedelta(days=30)).isoformat(),
            },
        ).json()

        # 1. Zero selections: should return 0 savings cleanly
        empty_res = client.post(
            "/api/v1/recurring-payments/simulate-cancellation",
            headers=owner_headers,
            json={"recurring_payment_ids": []},
        )
        assert empty_res.status_code == 200
        empty_data = empty_res.json()
        assert empty_data["selected_count"] == 0
        assert empty_data["monthly_savings"] == 0.0
        assert empty_data["annual_potential_savings"] == 0.0

        # 2. Duplicate selections: should deduplicate and avoid double counting
        dup_res = client.post(
            "/api/v1/recurring-payments/simulate-cancellation",
            headers=owner_headers,
            json={"recurring_payment_ids": [sub_monthly["id"], sub_monthly["id"]]},
        )
        assert dup_res.status_code == 200
        dup_data = dup_res.json()
        assert dup_data["selected_count"] == 1
        assert dup_data["monthly_savings"] == 600.0
        assert dup_data["annual_potential_savings"] == 7200.0

        # 3. Annual frequency normalization: 1200 annual -> 100/mo savings
        annual_res = client.post(
            "/api/v1/recurring-payments/simulate-cancellation",
            headers=owner_headers,
            json={"recurring_payment_ids": [sub_annual["id"]]},
        )
        assert annual_res.status_code == 200
        annual_data = annual_res.json()
        assert annual_data["selected_count"] == 1
        assert annual_data["monthly_savings"] == 100.0
        assert annual_data["annual_potential_savings"] == 1200.0

        # 4. Multi-selection combined savings: 600 + 100 = 700/mo (8400/yr)
        multi_res = client.post(
            "/api/v1/recurring-payments/simulate-cancellation",
            headers=owner_headers,
            json={"recurring_payment_ids": [sub_monthly["id"], sub_annual["id"]]},
        )
        assert multi_res.status_code == 200
        multi_data = multi_res.json()
        assert multi_data["selected_count"] == 2
        assert multi_data["monthly_savings"] == 700.0
        assert multi_data["annual_potential_savings"] == 8400.0

        # 5. User-added items have None engagement status (insufficient data / no ML inference)
        assert sub_monthly["transactional_engagement_status"] is None
        assert sub_monthly["transactional_engagement_explanation"] is None
    finally:
        cleanup(owner_email)

