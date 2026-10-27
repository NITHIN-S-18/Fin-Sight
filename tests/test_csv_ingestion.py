from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.database.models.financial_profile import FinancialProfile
from app.main import app
from app.ml.feature_engineering import FeatureEngineeringPipeline
from app.services.dataset_service import get_dataset_service


client = TestClient(app)


def create_account() -> tuple[str, dict[str, str], str]:
    email = f"csv-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    assert client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    ).status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    with SessionLocal() as session:
        user_id = session.query(AuthUser).filter(AuthUser.email == email).one().financial_user_id
    return email, {"Authorization": f"Bearer {token}"}, user_id


def remove_account(email: str) -> None:
    with SessionLocal() as session:
        account = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if account is not None:
            session.delete(account)
            session.commit()


def upload(headers: dict[str, str], filename: str, content: bytes):
    return client.post(
        "/api/v1/transactions/upload",
        files={"file": (filename, BytesIO(content), "text/csv")},
        headers=headers,
    )


def test_valid_multi_month_upload_appends_and_records_history():
    email, headers, user_id = create_account()
    try:
        first = upload(
            headers,
            "january.csv",
            b"transaction_date,amount,merchant_name\n"
            b"2026-01-05,100.00,January Merchant\n",
        )
        second = upload(
            headers,
            "february.csv",
            b"transaction_date,amount,merchant_name\n"
            b"2026-02-05,200.00,February Merchant\n",
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["accepted_count"] == 1
        assert second.json()["accepted_count"] == 1
        transactions = client.get(
            f"/api/v1/dataset/user/{user_id}/transactions",
            headers=headers,
        ).json()
        assert {row["merchant_name"] for row in transactions} == {
            "January Merchant",
            "February Merchant",
        }
        history = client.get("/api/v1/transactions/imports", headers=headers).json()
        assert [row["file_name"] for row in history] == ["february.csv", "january.csv"]
        assert all(row["status"] == "processed" for row in history)
    finally:
        remove_account(email)


def test_duplicate_rows_and_repeated_file_upload_are_not_appended():
    email, headers, user_id = create_account()
    content = (
        b"transaction_date,amount,merchant_name\n"
        b"2026-03-05,100.00,Same Merchant\n"
        b"2026-03-05,100.00,Same Merchant\n"
    )
    try:
        first = upload(headers, "march.csv", content)
        repeated = upload(headers, "march-copy.csv", content)

        assert first.status_code == 201
        assert first.json()["accepted_count"] == 1
        assert first.json()["duplicate_count"] == 1
        assert repeated.status_code == 201
        assert repeated.json()["accepted_count"] == 0
        assert repeated.json()["duplicate_count"] == 2
        assert len(
            client.get(
                f"/api/v1/dataset/user/{user_id}/transactions",
                headers=headers,
            ).json()
        ) == 1
    finally:
        remove_account(email)


def test_invalid_rows_reject_the_whole_file_without_partial_persistence():
    email, headers, user_id = create_account()
    try:
        response = upload(
            headers,
            "invalid-rows.csv",
            b"transaction_date,amount\n"
            b"2026-04-01,not-a-number\n"
            b"not-a-date,10.00\n"
            b"2026-04-03,\n",
        )

        assert response.status_code == 422
        assert "Row 2" in str(response.json())
        assert "Row 3" in str(response.json())
        assert "Row 4" in str(response.json())
        assert client.get(
            f"/api/v1/dataset/user/{user_id}/transactions",
            headers=headers,
        ).json() == []
        assert client.get("/api/v1/transactions/imports", headers=headers).json() == []
    finally:
        remove_account(email)


def test_unsupported_duplicate_and_malformed_schemas_are_rejected():
    email, headers, _ = create_account()
    try:
        unsupported = upload(
            headers,
            "unsupported.csv",
            b"transaction_date,amount,account_balance\n2026-05-01,10,100\n",
        )
        duplicate_header = upload(
            headers,
            "duplicate-header.csv",
            b"transaction_date,amount,amount\n2026-05-01,10,20\n",
        )
        malformed_row = upload(
            headers,
            "malformed-row.csv",
            b"transaction_date,amount,merchant_name\n2026-05-01,10\n",
        )
        malformed_csv = upload(
            headers,
            "malformed-csv.csv",
            b"transaction_date,amount,merchant_name\n"
            b'2026-05-01,10,"unterminated\n',
        )

        assert unsupported.status_code == 422
        assert duplicate_header.status_code == 422
        assert malformed_row.status_code == 422
        assert malformed_csv.status_code == 422
    finally:
        remove_account(email)


def test_non_csv_upload_and_missing_required_columns_are_rejected():
    email, headers, _ = create_account()
    try:
        non_csv = upload(headers, "transactions.txt", b"transaction_date,amount\n2026-01-01,10\n")
        missing_date = upload(headers, "missing-date.csv", b"amount\n10\n")
        missing_amount = upload(headers, "missing-amount.csv", b"transaction_date\n2026-01-01\n")

        assert non_csv.status_code == 422
        assert missing_date.status_code == 422
        assert missing_amount.status_code == 422
    finally:
        remove_account(email)


def test_upload_synchronizes_profile_from_complete_ledger_and_ml_features():
    email, headers, user_id = create_account()
    csv_a = (
        b"transaction_date,amount,merchant_name,transaction_class,frequency,commitment_type,transaction_status\n"
        b"2026-06-01,60000,Employer,income,Monthly,,Success\n"
        b"2026-06-02,499,Netflix,subscription,Monthly,Optional,Success\n"
    )
    csv_b = (
        b"transaction_date,amount,merchant_name,transaction_class,frequency,commitment_type,transaction_status\n"
        b"2026-07-01,12000,Home Loan,emi,Monthly,Mandatory,Success\n"
        b"2026-07-02,2500,Paytm Postpaid,bnpl,Monthly,Mandatory,Success\n"
    )
    try:
        assert upload(headers, "a.csv", csv_a).status_code == 201
        assert upload(headers, "b.csv", csv_b).status_code == 201
        assert upload(headers, "b-copy.csv", csv_b).json()["duplicate_count"] == 2

        with SessionLocal() as session:
            profile = session.query(FinancialProfile).filter_by(user_id=user_id).one()
            assert profile.monthly_income == 60000
            assert profile.financial_capacity == 60000
            # UnifiedCommitmentService counts persisted eligible recurring
            # obligations, not one-off uploaded rows without recurring records.
            assert profile.subscription_burden == 0
            assert profile.emi_burden == 0
            assert profile.bnpl_burden == 0
            assert profile.monthly_commitments == 0
            assert profile.active_subscriptions == 0
            assert profile.active_emis == 0
            assert profile.active_bnpl == 0
            assert profile.total_transactions == 4
            assert profile.exposure_score == 0.0

        dataset_service = get_dataset_service()
        features = FeatureEngineeringPipeline().build_user_feature_frame(dataset_service, user_id)
        row = features.data.iloc[0]
        assert row["commitment_ratio"] == 0
        assert row["exposure_utilization"] == 0
        assert len(row) == len(FeatureEngineeringPipeline().features)
    finally:
        remove_account(email)
