"""Comprehensive integration and unit test suite for the Intelligent Data Import Pipeline (CSV & PDF)."""
from __future__ import annotations

import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
try:
    from pypdf import PdfWriter
    HAS_PYPDF = True
except ImportError:
    PdfWriter = None
    HAS_PYPDF = False

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.database.models.transaction import Transaction
from app.main import app

client = TestClient(app)


def create_account() -> tuple[str, dict[str, str], str]:
    email = f"import-test-{uuid4().hex}@example.com"
    password = "Correct-Horse-Battery-42!"
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Import Tester"},
    )
    assert res.status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    with SessionLocal() as session:
        user_id = session.query(AuthUser).filter(AuthUser.email == email).one().financial_user_id
    return email, {"Authorization": f"Bearer {token}"}, user_id


def remove_account(email: str) -> None:
    with SessionLocal() as session:
        acc = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if acc is not None:
            session.delete(acc)
            session.commit()


def create_synthetic_pdf(lines: list[str]) -> bytes:
    """Creates a valid text-based PDF statement using pypdf."""
    from pypdf.generic import DictionaryObject, NameObject, NumberObject, ArrayObject, DecodedStreamObject
    # We can write an uncompressed PDF stream
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    # Using text insertion with explicit font leading and newlines
    content_text = "BT\n/F1 12 Tf\n16 TL\n50 750 Td\n"
    for l in lines:
        safe_l = l.replace("(", "\\(").replace(")", "\\)")
        content_text += f"({safe_l}) Tj\nT*\n"
    content_text += "ET\n"

    page = writer.pages[0]
    stream = DecodedStreamObject()
    stream.set_data(content_text.encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)

    # Set basic font resource
    font_dict = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_res = DictionaryObject({NameObject("/F1"): writer._add_object(font_dict)})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): font_res})

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ==============================================================================
# 1. PREVIEW & CONFIRMATION STAGED WORKFLOW
# ==============================================================================

def test_preview_does_not_persist_and_confirm_persists():
    email, headers, user_id = create_account()
    csv_data = (
        b"Date,Description,Deposits,Withdrawls,Balance\n"
        b"20-Aug-2020,Salary Credit,50000.00,0.00,50000.00\n"
        b"22-Aug-2020,Netflix Subscription,0.00,499.00,49501.00\n"
    )
    try:
        # Step 1: Request Preview
        prev_res = client.post(
            "/api/v1/transactions/preview",
            files={"file": ("dataset_a.csv", io.BytesIO(csv_data), "text/csv")},
            headers=headers,
        )
        assert prev_res.status_code == 200
        preview = prev_res.json()
        assert preview["file_type"] == "csv"
        assert preview["valid_rows_count"] == 2
        assert preview["total_credits"] == 50000.00
        assert preview["total_debits"] == 499.00
        assert preview["preview_token"] is not None

        # Verify nothing persisted during preview
        with SessionLocal() as session:
            txs = session.query(Transaction).filter_by(user_id=user_id).all()
            assert len(txs) == 0

        # Step 2: Confirm Import using preview token
        conf_res = client.post(
            "/api/v1/transactions/confirm",
            json={"preview_token": preview["preview_token"]},
            headers=headers,
        )
        assert conf_res.status_code == 201
        conf_data = conf_res.json()
        assert conf_data["accepted_count"] == 2
        assert conf_data["duplicate_count"] == 0

        # Verify transactions are now safely persisted
        with SessionLocal() as session:
            txs = session.query(Transaction).filter_by(user_id=user_id).all()
            assert len(txs) == 2
            assert any(t.amount == 50000.00 and t.income_flag is True for t in txs)
            assert any(t.amount == 499.00 and t.income_flag is False for t in txs)
    finally:
        remove_account(email)


# ==============================================================================
# 2. REPRESENTATIVE DATASET A & DATASET B COMPATIBILITY
# ==============================================================================

def test_dataset_a_compatibility_dual_amounts_and_dated_format():
    """Format A: Date (20-Aug-2020), Description, Deposits, Withdrawls, Balance."""
    email, headers, user_id = create_account()
    csv_data = (
        b"Date,Description,Deposits,Withdrawls,Balance\n"
        b"20-Aug-2020,Monthly Salary,65000.00,00.00,65000.00\n"
        b"25-Aug-2020,HDFC Home Loan EMI,0.00,15000.00,50000.00\n"
        b"28-Aug-2020,Zomato Online Food,0.00,850.50,49149.50\n"
    )
    try:
        res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("statement_format_a.csv", io.BytesIO(csv_data), "text/csv")},
            headers=headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["accepted_count"] == 3
        assert data["duplicate_count"] == 0

        with SessionLocal() as session:
            txs = session.query(Transaction).filter_by(user_id=user_id).order_by(Transaction.transaction_date).all()
            assert len(txs) == 3
            # Check date parsed into 2020-08-20
            assert txs[0].transaction_date.strftime("%Y-%m-%d") == "2020-08-20"
            assert txs[0].amount == 65000.00
            assert txs[0].income_flag is True
            # Check EMI detection
            assert txs[1].amount == 15000.00
            assert txs[1].income_flag is False
            assert txs[1].transaction_class == "emi"
    finally:
        remove_account(email)


def test_dataset_b_compatibility_explicit_types_and_timestamps():
    """Format B: type, mode, amount, currentBalance, transactionTimestamp, txnId, narration, reference."""
    email, headers, user_id = create_account()
    csv_data = (
        b"type,mode,amount,currentBalance,transactionTimestamp,valueDate,txnId,narration,reference\n"
        b"CREDIT,UPI,45000.00,45000.00,2026-03-01T10:15:30+05:30,2026-03-01,TXN99881,TechCorp Salary,REF1001\n"
        b"DEBIT,CARD,599.00,44401.00,2026-03-05T14:20:00+05:30,2026-03-05,TXN99882,Spotify Music,REF1002\n"
        b"DEBIT,UPI,1200.00,43201.00,2026-03-10T19:00:00+05:30,2026-03-10,TXN99883,Simpl Pay,REF1003\n"
    )
    try:
        res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("statement_format_b.csv", io.BytesIO(csv_data), "text/csv")},
            headers=headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["accepted_count"] == 3

        with SessionLocal() as session:
            txs = session.query(Transaction).filter_by(user_id=user_id).all()
            assert len(txs) == 3
            salary = next(t for t in txs if t.amount == 45000.00)
            assert salary.income_flag is True
            assert salary.category == "income"

            spotify = next(t for t in txs if t.amount == 599.00)
            assert spotify.income_flag is False
            assert spotify.transaction_class == "subscription"

            simpl = next(t for t in txs if t.amount == 1200.00)
            assert simpl.income_flag is False
            assert simpl.transaction_class == "bnpl"
    finally:
        remove_account(email)


# ==============================================================================
# 3. TEXT-BASED PDF STATEMENT INGESTION
# ==============================================================================

def test_text_pdf_statement_extraction_and_ingestion():
    email, headers, user_id = create_account()
    statement_lines = [
        "FinSight Bank - Account Statement",
        "Account Number: 9876543210",
        "--------------------------------------------------",
        "2026-04-01 Monthly Salary Credit 75000.00 CR 75000.00",
        "2026-04-05 Netflix Premium 649.00 DR 74351.00",
        "2026-04-12 HDFC Loan Repayment 12500.00 DR 61851.00",
    ]
    pdf_bytes = create_synthetic_pdf(statement_lines)
    try:
        # Preview PDF
        prev = client.post(
            "/api/v1/transactions/preview",
            files={"file": ("bank_statement.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            headers=headers,
        )
        assert prev.status_code == 200
        pdata = prev.json()
        assert pdata["file_type"] == "pdf"
        assert pdata["valid_rows_count"] == 3
        assert pdata["preview_token"] is not None

        # Confirm PDF
        conf = client.post(
            "/api/v1/transactions/confirm",
            json={"preview_token": pdata["preview_token"]},
            headers=headers,
        )
        assert conf.status_code == 201
        assert conf.json()["accepted_count"] == 3

        with SessionLocal() as session:
            txs = session.query(Transaction).filter_by(user_id=user_id).all()
            assert len(txs) == 3
    finally:
        remove_account(email)


# ==============================================================================
# 4. CROSS-FORMAT DEDUPLICATION & REPEATED UPLOADS
# ==============================================================================

def test_cross_format_deduplication_between_csv_and_pdf():
    email, headers, user_id = create_account()
    # First upload via CSV
    csv_data = (
        b"transaction_date,amount,description,transaction_class\n"
        b"2026-04-01,75000.00,Monthly Salary Credit,income\n"
    )
    pdf_lines = [
        "2026-04-01 Monthly Salary Credit 75000.00 CR 75000.00",
    ]
    pdf_bytes = create_synthetic_pdf(pdf_lines)
    try:
        res1 = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("first.csv", io.BytesIO(csv_data), "text/csv")},
            headers=headers,
        )
        assert res1.status_code == 201
        assert res1.json()["accepted_count"] == 1

        # Now upload the identical transaction via PDF
        res2 = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("second.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            headers=headers,
        )
        assert res2.status_code == 201
        data2 = res2.json()
        assert data2["accepted_count"] == 0
        assert data2["duplicate_count"] == 1

        with SessionLocal() as session:
            txs = session.query(Transaction).filter_by(user_id=user_id).all()
            assert len(txs) == 1
    finally:
        remove_account(email)


# ==============================================================================
# 5. MULTI-USER ISOLATION & SECURITY
# ==============================================================================

def test_multi_user_isolation_during_import():
    user1_email, user1_headers, user1_id = create_account()
    user2_email, user2_headers, user2_id = create_account()
    shared_csv = (
        b"transaction_date,amount,merchant_name\n"
        b"2026-05-10,350.00,Cafe Coffee Day\n"
    )
    try:
        # User 1 imports
        r1 = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("coffee.csv", io.BytesIO(shared_csv), "text/csv")},
            headers=user1_headers,
        )
        assert r1.status_code == 201
        assert r1.json()["accepted_count"] == 1

        # User 2 imports the same CSV
        r2 = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("coffee.csv", io.BytesIO(shared_csv), "text/csv")},
            headers=user2_headers,
        )
        assert r2.status_code == 201
        assert r2.json()["accepted_count"] == 1  # Not treated as duplicate for User 2!

        # Check isolated counts in database
        with SessionLocal() as session:
            txs1 = session.query(Transaction).filter_by(user_id=user1_id).all()
            txs2 = session.query(Transaction).filter_by(user_id=user2_id).all()
            assert len(txs1) == 1
            assert len(txs2) == 1
    finally:
        remove_account(user1_email)
        remove_account(user2_email)


# ==============================================================================
# 6. FRACTIONAL MONETARY CAPACITY (42057.05) & DOWNSTREAM SERVICES
# ==============================================================================

def test_fractional_monetary_capacity_in_profile_and_dashboard():
    """Verify that fractional values like 42057.05 do not crash UserFinancialProfileResponse, Dashboard, or Simulator."""
    email, headers, user_id = create_account()
    # CSV with fractional salary credit that averages to 42057.05
    csv_data = (
        b"Date,Description,Deposits,Withdrawls,Balance\n"
        b"20-Aug-2020,Salary Credit,42057.05,00.00,42057.05\n"
        b"22-Aug-2020,Netflix Premium,0.00,499.00,41558.05\n"
    )
    try:
        upload_res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("fractional.csv", io.BytesIO(csv_data), "text/csv")},
            headers=headers,
        )
        assert upload_res.status_code == 201

        # 1. Verify UserResponse & UserFinancialProfileResponse serialization
        user_res = client.get(f"/api/v1/dataset/user/{user_id}", headers=headers)
        assert user_res.status_code == 200
        user_data = user_res.json()
        assert user_data["financial_profile"] is not None
        assert abs(user_data["financial_profile"]["monthly_financial_capacity"] - 42057.05) < 0.01

        # 2. Verify Dashboard endpoint does not return HTTP 500
        dash_res = client.get(f"/api/v1/dashboard/{user_id}", headers=headers)
        assert dash_res.status_code == 200
        dash_data = dash_res.json()
        assert "exposure_card" in dash_data
        assert abs(dash_data["exposure_card"]["monthly_financial_capacity"] - 42057.05) < 0.01

        # 3. Verify Exposure endpoint does not return HTTP 500
        expo_res = client.get(f"/api/v1/exposure/{user_id}", headers=headers)
        assert expo_res.status_code == 200
        expo_data = expo_res.json()
        assert abs(expo_data["current_financial_status"]["monthly_financial_capacity"] - 42057.05) < 0.01

        # 4. Verify What-If Simulator endpoint does not return HTTP 500
        sim_res = client.post(
            "/api/v1/simulator/simulate",
            json={
                "scenario_type": "add_subscription",
                "parameters": {"monthly_cost": 500.0},
            },
            headers=headers,
        )
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        assert sim_data["baseline_health"] is not None
        assert sim_data["projected_health"] is not None

        # 5. Verify Copilot conversations endpoint does not return HTTP 500
        conv_res = client.get("/api/v1/copilot/conversations", headers=headers)
        assert conv_res.status_code == 200
        assert isinstance(conv_res.json(), list)
    finally:
        remove_account(email)
