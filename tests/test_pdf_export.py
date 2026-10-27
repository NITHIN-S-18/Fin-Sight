from __future__ import annotations

import json
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.database.models.financial_goal import FinancialGoal
from app.main import app

client = TestClient(app)


def _create_user() -> tuple[str, dict[str, str], str]:
    email = f"pdf-test-{uuid4().hex}@example.com"
    password = "correct-horse-battery"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201, reg.text
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    with SessionLocal() as session:
        user_id = session.query(AuthUser).filter(AuthUser.email == email).one().financial_user_id
    return email, {"Authorization": f"Bearer {token}"}, user_id


def _cleanup_user(email: str) -> None:
    with SessionLocal() as session:
        user = session.query(AuthUser).filter(AuthUser.email == email).one_or_none()
        if user is not None:
            session.delete(user)
            session.commit()


def test_pdf_export_unauthenticated_returns_401() -> None:
    """Unauthenticated requests to the export endpoint must return 401 Unauthorized."""
    response = client.get("/api/v1/auth/export?format=pdf")
    assert response.status_code == 401


def test_pdf_export_empty_user_generates_valid_pdf() -> None:
    """An authenticated user with no transaction records must receive a valid, clean PDF report."""
    email, headers, user_id = _create_user()
    try:
        response = client.get("/api/v1/auth/export?format=pdf", headers=headers)
        assert response.status_code == 200, response.text
        assert response.headers.get("content-type") == "application/pdf"
        assert "FinSight_Financial_Report_" in response.headers["Content-Disposition"]
        assert response.headers["Content-Disposition"].endswith('.pdf"')

        content = response.content
        assert content.startswith(b"%PDF-"), "Response must start with PDF magic bytes"
        assert len(content) > 1000, "PDF should have substantial content"
    finally:
        _cleanup_user(email)


def test_pdf_export_user_with_transactions_and_commitments() -> None:
    """An authenticated user with transactions and recurring obligations receives a complete multi-page PDF."""
    email, headers, user_id = _create_user()
    try:
        # Upload transactions with income, subscriptions, and living expenses
        rows = [
            "transaction_date,amount,merchant_name,transaction_class,category,transaction_status",
            "2026-01-01,60000,Corporate Payroll,Income,Salary,success",
            "2026-01-05,1499,Netflix India,Subscription,Entertainment,success",
            "2026-01-10,4500,Supermarket Groceries,Expense,Groceries,success",
            "2026-02-01,60000,Corporate Payroll,Income,Salary,success",
            "2026-02-05,1499,Netflix India,Subscription,Entertainment,success",
            "2026-02-12,3800,Supermarket Groceries,Expense,Groceries,success",
            "2026-03-01,60000,Corporate Payroll,Income,Salary,success",
            "2026-03-05,1499,Netflix India,Subscription,Entertainment,success",
            "2026-03-15,4200,Supermarket Groceries,Expense,Groceries,success",
        ]
        csv_bytes = ("\n".join(rows) + "\n").encode()
        upload_res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("test_report_transactions.csv", BytesIO(csv_bytes), "text/csv")},
            headers=headers,
        )
        assert upload_res.status_code == 201, upload_res.text

        # Add a financial goal
        with SessionLocal() as session:
            goal = FinancialGoal(
                user_id=user_id,
                goal_name="Emergency Reserve",
                goal_amount=100000.0,
                timeframe_months=12,
                is_active=True,
                evaluation={
                    "goal_name": "Emergency Reserve",
                    "goal_amount": 100000.0,
                    "goal_months": 12,
                    "goal_feasible": True,
                    "required_monthly_saving": 8333.33,
                    "expected_monthly_saving": 35000.0,
                    "explanation": "Feasible based on monthly capacity",
                },
            )
            session.add(goal)
            session.commit()

        # Export PDF
        response = client.get("/api/v1/auth/export?format=pdf", headers=headers)
        assert response.status_code == 200, response.text
        assert response.headers.get("content-type") == "application/pdf"
        assert response.content.startswith(b"%PDF-")
        assert len(response.content) > 5000, "Rich PDF report must contain full analysis and exceed 5KB"
    finally:
        _cleanup_user(email)


def test_tenant_isolation_user_cannot_export_another_users_data() -> None:
    """User A's PDF export must derive identity strictly from User A's token, never accessing User B's records."""
    email_a, headers_a, user_id_a = _create_user()
    email_b, headers_b, user_id_b = _create_user()
    try:
        # Upload transactions only for User A
        rows_a = [
            "transaction_date,amount,merchant_name,transaction_class,category,transaction_status",
            "2026-01-01,75000,Specialized Employer A,Income,Salary,success",
            "2026-01-10,2500,Private Club Membership A,Subscription,Entertainment,success",
        ]
        upload_a = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("txns_a.csv", BytesIO(("\n".join(rows_a) + "\n").encode()), "text/csv")},
            headers=headers_a,
        )
        assert upload_a.status_code == 201, upload_a.text

        # User A's PDF
        pdf_a = client.get("/api/v1/auth/export?format=pdf", headers=headers_a)
        assert pdf_a.status_code == 200
        assert pdf_a.content.startswith(b"%PDF-")

        # User B's PDF (has no transactions uploaded)
        pdf_b = client.get("/api/v1/auth/export?format=pdf", headers=headers_b)
        assert pdf_b.status_code == 200
        assert pdf_b.content.startswith(b"%PDF-")

        # Verify JSON export isolation as ground truth
        json_a = client.get("/api/v1/auth/export?format=json", headers=headers_a).json()
        json_b = client.get("/api/v1/auth/export?format=json", headers=headers_b).json()

        assert json_a["user_id"] == user_id_a
        assert json_a["transaction_count"] == 2
        assert json_b["user_id"] == user_id_b
        assert json_b["transaction_count"] == 0
    finally:
        _cleanup_user(email_a)
        _cleanup_user(email_b)


def test_existing_json_and_csv_exports_remain_operational() -> None:
    """Verify regression safety: JSON and CSV exports continue to work seamlessly alongside PDF."""
    email, headers, user_id = _create_user()
    try:
        rows = [
            "transaction_date,amount,merchant_name,transaction_class,category,transaction_status",
            "2026-01-01,50000,Salary Deposit,Income,Salary,success",
            "2026-01-15,3000,Supermarket,Expense,Groceries,success",
        ]
        upload_res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("sample.csv", BytesIO(("\n".join(rows) + "\n").encode()), "text/csv")},
            headers=headers,
        )
        assert upload_res.status_code == 201

        # JSON export test
        res_json = client.get("/api/v1/auth/export?format=json", headers=headers)
        assert res_json.status_code == 200
        assert res_json.headers.get("content-type") == "application/json"
        data_json = res_json.json()
        assert data_json["user_id"] == user_id
        assert data_json["transaction_count"] == 2
        assert "finsight_financial_export.json" in res_json.headers.get("content-disposition", "")

        # CSV export test (explicit format=csv)
        res_csv = client.get("/api/v1/auth/export?format=csv", headers=headers)
        assert res_csv.status_code == 200
        assert res_csv.headers.get("content-type") == "text/csv; charset=utf-8" or "text/csv" in res_csv.headers.get("content-type", "")
        csv_text = res_csv.text
        assert "transaction_id,transaction_date,merchant_name" in csv_text
        assert "finsight_transactions.csv" in res_csv.headers.get("content-disposition", "")

        # CSV export test (default format)
        res_default = client.get("/api/v1/auth/export", headers=headers)
        assert res_default.status_code == 200
        assert "transaction_id,transaction_date" in res_default.text
    finally:
        _cleanup_user(email)


def test_pdf_export_invalid_token_returns_json_error_not_pdf() -> None:
    """Invalid credentials return 401 JSON error and must never return an application/pdf body."""
    response = client.get("/api/v1/auth/export?format=pdf", headers={"Authorization": "Bearer invalid.token.payload"})
    assert response.status_code == 401
    assert response.headers.get("content-type") == "application/json"
    assert not response.content.startswith(b"%PDF-")
    body = response.json()
    assert "detail" in body or "message" in body


def test_pdf_export_user_with_full_history_and_active_shortfall_model() -> None:
    """PDF export must succeed when user has 6+ months of history and Model 4 shortfall model is active."""
    email, headers, user_id = _create_user()
    try:
        rows = [
            "transaction_date,amount,merchant_name,transaction_class,category,transaction_status",
            "2025-08-01,70000,Employer Corp,Income,Salary,success",
            "2025-08-05,1500,Streaming Service,Subscription,Entertainment,success",
            "2025-08-10,5000,Grocery Store,Expense,Groceries,success",
            "2025-09-01,70000,Employer Corp,Income,Salary,success",
            "2025-09-05,1500,Streaming Service,Subscription,Entertainment,success",
            "2025-09-10,5200,Grocery Store,Expense,Groceries,success",
            "2025-10-01,70000,Employer Corp,Income,Salary,success",
            "2025-10-05,1500,Streaming Service,Subscription,Entertainment,success",
            "2025-10-10,4800,Grocery Store,Expense,Groceries,success",
            "2025-11-01,70000,Employer Corp,Income,Salary,success",
            "2025-11-05,1500,Streaming Service,Subscription,Entertainment,success",
            "2025-11-10,5100,Grocery Store,Expense,Groceries,success",
            "2025-12-01,70000,Employer Corp,Income,Salary,success",
            "2025-12-05,1500,Streaming Service,Subscription,Entertainment,success",
            "2025-12-10,6000,Grocery Store,Expense,Groceries,success",
            "2026-01-01,70000,Employer Corp,Income,Salary,success",
            "2026-01-05,1500,Streaming Service,Subscription,Entertainment,success",
            "2026-01-10,5300,Grocery Store,Expense,Groceries,success",
            "2026-02-01,70000,Employer Corp,Income,Salary,success",
            "2026-02-05,1500,Streaming Service,Subscription,Entertainment,success",
            "2026-02-10,5200,Grocery Store,Expense,Groceries,success",
        ]
        csv_bytes = ("\n".join(rows) + "\n").encode()
        upload_res = client.post(
            "/api/v1/transactions/upload",
            files={"file": ("full_history.csv", BytesIO(csv_bytes), "text/csv")},
            headers=headers,
        )
        assert upload_res.status_code == 201

        # Request PDF export
        response = client.get("/api/v1/auth/export?format=pdf", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        assert response.content.startswith(b"%PDF-")
        assert len(response.content) > 10000, "Full history report must be comprehensive"

        # Request JSON export
        res_json = client.get("/api/v1/auth/export?format=json", headers=headers)
        assert res_json.status_code == 200
        assert res_json.headers.get("content-type") == "application/json"
        data = res_json.json()
        assert data["user_id"] == user_id
        assert data["transaction_count"] == 21
    finally:
        _cleanup_user(email)


