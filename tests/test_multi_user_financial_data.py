from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.database.models.user import User
from app.main import app
from app.services.dataset_service import get_dataset_service


client = TestClient(app)


def create_account() -> tuple[str, dict[str, str], str]:
    email = f"tenant-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post("/api/v1/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    with SessionLocal() as session:
        financial_user_id = session.query(AuthUser).filter(AuthUser.email == email).one().financial_user_id
    return email, {"Authorization": f"Bearer {token}"}, financial_user_id


def test_new_account_is_empty_and_uploads_are_owned_and_deduplicated():
    email, headers, user_id = create_account()
    csv = b"transaction_date,amount,merchant_name\n2026-06-01,10.00,Netflix\n2026-06-02,20.00,Coffee\n"
    try:
        assert client.get(f"/api/v1/dataset/user/{user_id}/transactions", headers=headers).json() == []
        upload = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("june.csv", BytesIO(csv), "text/csv")},
            headers=headers,
        )
        assert upload.status_code == 201
        assert upload.json()["accepted_count"] == 2
        duplicate = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("copy.csv", BytesIO(csv), "text/csv")},
            headers=headers,
        )
        assert duplicate.json()["duplicate_count"] == 2
        assert len(client.get(f"/api/v1/dataset/user/{user_id}/transactions", headers=headers).json()) == 2
        history = client.get("/api/v1/transactions/imports", headers=headers).json()
        assert history[0]["transaction_start_date"].startswith("2026-06-01")
        assert history[0]["transaction_end_date"].startswith("2026-06-02")
    finally:
        with SessionLocal() as session:
            account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
            if account is not None:
                session.delete(account)
                session.commit()


def test_invalid_csv_is_rejected_and_accounts_are_isolated():
    email_a, headers_a, user_id_a = create_account()
    email_b, headers_b, user_id_b = create_account()
    try:
        invalid = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("bad.csv", BytesIO(b"transaction_date,amount\nnot-a-date,nope\n"), "text/csv")},
            headers=headers_a,
        )
        assert invalid.status_code == 422
        assert client.get(f"/api/v1/dataset/user/{user_id_b}/transactions", headers=headers_a).status_code == 403
        assert client.get(f"/api/v1/dataset/user/{user_id_a}/transactions", headers=headers_b).status_code == 403
    finally:
        with SessionLocal() as session:
            for email in (email_a, email_b):
                account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
                if account is not None:
                    session.delete(account)
            session.commit()


def test_copilot_rejects_spoofed_financial_user_id():
    email_a, headers_a, user_id_a = create_account()
    email_b, _, user_id_b = create_account()
    try:
        response = client.post(
            "/api/v1/copilot/query",
            headers=headers_a,
            json={"user_id": user_id_b, "question": "What is my exposure?"},
        )
        assert response.status_code == 403
        assert user_id_a != user_id_b
    finally:
        with SessionLocal() as session:
            for email in (email_a, email_b):
                account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
                if account is not None:
                    session.delete(account)
            session.commit()


def test_two_accounts_are_isolated_across_financial_surfaces():
    email_a, headers_a, user_id_a = create_account()
    email_b, headers_b, user_id_b = create_account()
    csv_a = (
        b"transaction_date,amount,merchant_name,transaction_class,frequency,recurring_flag\n"
        b"2026-10-01,499.00,Account A Streaming,Subscription,Monthly,Yes\n"
    )
    csv_b = (
        b"transaction_date,amount,merchant_name,transaction_class,frequency,recurring_flag\n"
        b"2026-10-01,799.00,Account B Streaming,Subscription,Monthly,Yes\n"
    )
    try:
        upload_a = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("a.csv", BytesIO(csv_a), "text/csv")},
            headers=headers_a,
        )
        upload_b = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("b.csv", BytesIO(csv_b), "text/csv")},
            headers=headers_b,
        )
        assert upload_a.status_code == 201, upload_a.text
        assert upload_b.status_code == 201, upload_b.text

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
        assert {row["merchant_name"] for row in transactions_a.json()} == {"Account A Streaming"}
        assert {row["merchant_name"] for row in transactions_b.json()} == {"Account B Streaming"}

        imports_a = client.get("/api/v1/transactions/imports", headers=headers_a)
        imports_b = client.get("/api/v1/transactions/imports", headers=headers_b)
        assert imports_a.status_code == 200
        assert imports_b.status_code == 200
        assert [row["file_name"] for row in imports_a.json()] == ["a.csv"]
        assert [row["file_name"] for row in imports_b.json()] == ["b.csv"]

        dashboard_a = client.get(f"/api/v1/dashboard/{user_id_a}", headers=headers_a)
        dashboard_b = client.get(f"/api/v1/dashboard/{user_id_b}", headers=headers_b)
        assert dashboard_a.status_code == 200
        assert dashboard_b.status_code == 200
        assert user_id_a in str(dashboard_a.json())
        assert user_id_b in str(dashboard_b.json())
        assert "Account B Streaming" not in str(dashboard_a.json())
        assert "Account A Streaming" not in str(dashboard_b.json())

        intelligence_a = client.get(f"/api/v1/ml/intelligence/{user_id_a}", headers=headers_a)
        intelligence_b = client.get(f"/api/v1/ml/intelligence/{user_id_b}", headers=headers_b)
        assert intelligence_a.status_code == 200
        assert intelligence_b.status_code == 200
        # A single uploaded transaction is not an eligible persisted recurring
        # obligation under UnifiedCommitmentService semantics.
        assert intelligence_a.json()["current_state"]["monthly_commitments"] == 0.0
        assert intelligence_b.json()["current_state"]["monthly_commitments"] == 0.0

        commitments_a = client.get(f"/api/v1/subscriptions/{user_id_a}", headers=headers_a)
        commitments_b = client.get(f"/api/v1/subscriptions/{user_id_b}", headers=headers_b)
        assert commitments_a.status_code == 200
        assert commitments_b.status_code == 200
        assert "Account A Streaming" in str(commitments_a.json())
        assert "Account B Streaming" not in str(commitments_a.json())
        assert "Account B Streaming" in str(commitments_b.json())
        assert "Account A Streaming" not in str(commitments_b.json())

        protected_requests = (
            ("dataset", f"/api/v1/dataset/user/{user_id_b}"),
            ("transactions", f"/api/v1/dataset/user/{user_id_b}/transactions"),
            ("dashboard", f"/api/v1/dashboard/{user_id_b}"),
            ("subscriptions", f"/api/v1/subscriptions/{user_id_b}"),
            ("emis", f"/api/v1/emis/{user_id_b}"),
            ("bnpl", f"/api/v1/bnpl/{user_id_b}"),
            ("exposure", f"/api/v1/exposure/{user_id_b}"),
            ("distress", f"/api/v1/ml/distress/{user_id_b}"),
            ("forecast", f"/api/v1/ml/exposure/{user_id_b}"),
            ("persona", f"/api/v1/ml/persona/{user_id_b}"),
            ("anomaly", f"/api/v1/ml/anomaly/{user_id_b}"),
            ("intelligence", f"/api/v1/ml/intelligence/{user_id_b}"),
            ("suggestions", f"/api/v1/copilot/suggestions/{user_id_b}"),
        )
        for _, path in protected_requests:
            assert client.get(path, headers=headers_a).status_code == 403

        spoofed_upload = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("spoof.csv", BytesIO(csv_a), "text/csv")},
            headers=headers_a,
        )
        assert spoofed_upload.status_code == 201
        assert all(
            row["merchant_name"] == "Account A Streaming"
            for row in client.get(
                f"/api/v1/dataset/user/{user_id_a}/transactions",
                headers=headers_a,
            ).json()
        )
    finally:
        with SessionLocal() as session:
            for email in (email_a, email_b):
                account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
                if account is not None:
                    session.delete(account)
            session.commit()


def test_empty_dashboard_contains_no_reference_user_data():
    email, headers, user_id = create_account()
    try:
        response = client.get(f"/api/v1/dashboard/{user_id}", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["onboarding_required"] is True
        assert payload["user_profile"]["user_id"] == user_id
        assert payload["user_profile"]["financial_profile"] is None

        serialized_payload = str(payload)
        for reference_value in ("U001", "Self-Employed Users", "Jaipur", "Kitchen EMI"):
            assert reference_value not in serialized_payload

        dashboard_schema = client.get("/openapi.json").json()
        dashboard_path = dashboard_schema["paths"][f"/api/v1/dashboard/{{user_id}}"]["get"]
        assert "examples" not in dashboard_path.get("responses", {})
        assert "U001" not in str(dashboard_schema["components"]["schemas"].get("DashboardResponse", {}))
    finally:
        with SessionLocal() as session:
            account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
            if account is not None:
                session.delete(account)
                session.commit()


def test_upload_maps_transaction_type_to_transaction_class():
    email, headers, user_id = create_account()
    csv = (
        b"transaction_date,amount,merchant_name,description,transaction_type,frequency\n"
        b"2026-07-01,499.00,Netflix,monthly subscription,Subscription,Monthly\n"
    )
    try:
        response = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("swagger-failing.csv", BytesIO(csv), "text/csv")},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["accepted_count"] == 1

        transactions = client.get(
            f"/api/v1/dataset/user/{user_id}/transactions", headers=headers
        ).json()
        assert len(transactions) == 1
        assert transactions[0]["transaction_class"] == "Subscription"
        assert "transaction_type" not in transactions[0]
    finally:
        with SessionLocal() as session:
            account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
            if account is not None:
                session.delete(account)
                session.commit()


def test_orphaned_auth_account_resolves_dedicated_financial_user_for_upload():
    email, headers, user_id = create_account()
    csv = b"transaction_date,amount,merchant_name\n2026-08-01,25.00,Coffee\n"
    try:
        with SessionLocal() as session:
            account = session.query(AuthUser).filter(AuthUser.email == email).one()
            financial_user = session.query(User).filter(User.auth_user_id == account.id).one()
            session.delete(financial_user)
            session.commit()

        me = client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200, me.text
        assert me.json()["financial_user_id"] == user_id

        upload = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("recovered.csv", BytesIO(csv), "text/csv")},
            headers=headers,
        )
        assert upload.status_code == 201, upload.text

        with SessionLocal() as session:
            account = session.query(AuthUser).filter(AuthUser.email == email).one()
            recovered = session.query(User).filter(User.auth_user_id == account.id).one()
            assert recovered.user_id == user_id
            assert recovered.user_id != "U001"
    finally:
        with SessionLocal() as session:
            account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
            if account is not None:
                session.delete(account)
                session.commit()


def test_upload_refreshes_dataset_snapshot_for_dashboard_intelligence():
    email, headers, user_id = create_account()
    other_email, other_headers, other_user_id = create_account()
    csv = (
        b"transaction_date,amount,merchant_name,description,transaction_class,frequency,"
        b"recurring_flag,transaction_status\n"
        b"2026-09-01,499.00,Fresh Streaming,monthly subscription,Subscription,Monthly,Yes,Success\n"
    )
    try:
        warm_service = get_dataset_service()
        assert warm_service.get_user_transactions(user_id) == []

        before = client.get(f"/api/v1/dashboard/{user_id}", headers=headers)
        assert before.status_code == 200
        assert before.json()["onboarding_required"] is True

        upload = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("fresh.csv", BytesIO(csv), "text/csv")},
            headers=headers,
        )
        assert upload.status_code == 201, upload.text
        assert upload.json()["accepted_count"] == 1

        refreshed_service = get_dataset_service()
        assert refreshed_service is not warm_service
        assert len(refreshed_service.get_user_transactions(user_id)) == 1

        after = client.get(f"/api/v1/dashboard/{user_id}", headers=headers)
        assert after.status_code == 200, after.text
        dashboard = after.json()
        assert dashboard["user_profile"]["user_id"] == user_id
        assert dashboard["subscription_highlights"]["active_count"] == 1
        assert dashboard["subscription_highlights"]["most_expensive"]["merchant_name"] == "Fresh Streaming"
        assert client.get(
            f"/api/v1/dataset/user/{user_id}/transactions", headers=other_headers
        ).status_code == 403
        assert client.get(
            f"/api/v1/dataset/user/{other_user_id}/transactions", headers=headers
        ).status_code == 403
    finally:
        with SessionLocal() as session:
            for email_to_remove in (email, other_email):
                account = session.query(AuthUser).filter(AuthUser.email == email_to_remove).one_or_none()
                if account is not None:
                    session.delete(account)
            session.commit()


def test_24_uploaded_transactions_reach_all_dashboard_commitment_services():
    email, headers, user_id = create_account()
    other_email, other_headers, other_user_id = create_account()
    rows = []
    for month, day in ((6, 5), (7, 5), (8, 5)):
        rows.extend(
            [
                f"2026-{month:02d}-{day:02d},65000,Employer Salary,Monthly salary,income,Salary,,Monthly,Yes,Success",
                f"2026-{month:02d}-{day + 1:02d},499,Netflix,Monthly subscription,subscription,Netflix,,Monthly,Yes,Success",
                f"2026-{month:02d}-{day + 2:02d},12000,Home Loan,Monthly EMI,emi,Home Loan,,Monthly,Yes,Success",
                f"2026-{month:02d}-{day + 3:02d},2500,Paytm Postpaid,BNPL installment,bnpl,Pay Later,,Monthly,Yes,Success",
                f"2026-{month:02d}-{day + 4:02d},18000,House Rent,Monthly rent,housing,Rent,,Monthly,No,Success",
                f"2026-{month:02d}-{day + 5:02d},3200,DMart,Grocery purchase,grocery,Grocery,,Monthly,No,Success",
                f"2026-{month:02d}-{day + 6:02d},1450,BESCOM,Electricity bill,utility,Electricity,,Monthly,No,Success",
                f"2026-{month:02d}-{day + 7:02d},3000,Fuel Station,Fuel purchase,fuel,Fuel,,Monthly,No,Success",
            ]
        )
    csv = (
        b"transaction_date,amount,merchant_name,description,category,transaction_type,"
        b"commitment_type,frequency,recurring_flag,transaction_status\n"
        + "\n".join(rows).encode()
        + b"\n"
    )
    try:
        assert len(rows) == 24
        upload = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("three-months.csv", BytesIO(csv), "text/csv")},
            headers=headers,
        )
        assert upload.status_code == 201, upload.text
        assert upload.json()["accepted_count"] == 24

        dashboard = client.get(f"/api/v1/dashboard/{user_id}", headers=headers)
        assert dashboard.status_code == 200, dashboard.text
        payload = dashboard.json()
        assert payload["user_profile"]["user_id"] == user_id
        assert payload["user_profile"]["monthly_financial_capacity"] == 65000
        assert payload["subscription_highlights"]["active_count"] == 1
        assert payload["emi_highlights"]["active_count"] == 1
        assert payload["bnpl_highlights"]["active_providers_count"] == 1
        assert payload["quick_statistics"]["monthly_commitments_total"] > 0
        assert "U001" not in str(payload)

        assert client.get(
            f"/api/v1/dataset/user/{user_id}/transactions", headers=other_headers
        ).status_code == 403
        assert client.get(
            f"/api/v1/dataset/user/{other_user_id}/transactions", headers=headers
        ).status_code == 403
    finally:
        with SessionLocal() as session:
            for email_to_remove in (email, other_email):
                account = session.query(AuthUser).filter(AuthUser.email == email_to_remove).one_or_none()
                if account is not None:
                    session.delete(account)
            session.commit()
