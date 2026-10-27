from __future__ import annotations

import concurrent.futures
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import verify_password
from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.database.models.password_reset_otp import PasswordResetOTP
from app.database.models.password_reset_token import PasswordResetToken
from app.database.models.user import User
from app.main import app
from app.services.email_service import EmailDeliveryError, email_service
from app.services.rate_limiter import password_reset_rate_limiter


def _error_msg(res):
    return res.json().get("message") or res.json().get("detail") or ""


@pytest.fixture(autouse=True)
def reset_limiter_and_email():
    password_reset_rate_limiter.reset()
    email_service.clear_last_sent_email()
    original_provider = email_service.settings.email_delivery_provider
    email_service.settings.email_delivery_provider = "console"
    yield
    email_service.settings.email_delivery_provider = original_provider
    password_reset_rate_limiter.reset()
    email_service.clear_last_sent_email()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def test_user():
    email = f"reset-{uuid4().hex}@example.com"
    password = "InitialPassword123"
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Reset Test User"},
    )
    assert response.status_code == 201

    with SessionLocal() as session:
        user = session.query(AuthUser).filter(AuthUser.email == email).one()
        auth_user_id = user.id
        financial_user_id = user.financial_user.user_id if user.financial_user else None

    yield email, password, auth_user_id, financial_user_id

    with SessionLocal() as session:
        user = session.query(AuthUser).filter(AuthUser.id == auth_user_id).one_or_none()
        if user is not None:
            session.delete(user)
            session.commit()


# ==============================================================================
# 1. FORGOT PASSWORD (OTP GENERATION & ANTI-ENUMERATION)
# ==============================================================================

def test_forgot_password_generates_and_stores_hashed_otp(client: TestClient, test_user):
    email, _, auth_user_id, _ = test_user
    response = client.post("/api/v1/auth/forgot-password", json={"email": email})

    assert response.status_code == 200
    assert "If an account exists" in response.json()["message"]

    # Verify OTP created in database
    with SessionLocal() as session:
        challenges = session.query(PasswordResetOTP).filter(PasswordResetOTP.auth_user_id == auth_user_id).all()
        assert len(challenges) == 1
        challenge = challenges[0]
        assert challenge.is_verified is False
        assert challenge.attempts == 0
        assert challenge.max_attempts == 5
        assert challenge.expires_at > datetime.now(timezone.utc)
        assert "$" in challenge.otp_hash

    # Verify email was captured by dev/console service
    last_email = email_service.last_sent_email
    assert last_email is not None
    assert last_email["to"] == email
    otp = last_email["otp"]
    assert re.match(r"^\d{6}$", otp)

    # Verify stored hash matches SHA-256(otp:salt)
    salt, stored_hash = challenge.otp_hash.split("$", 1)
    expected_hash = hashlib.sha256(f"{otp}:{salt}".encode("utf-8")).hexdigest()
    assert stored_hash == expected_hash


def test_forgot_password_nonexistent_account(client: TestClient):
    nonexistent = f"nonexistent-{uuid4().hex}@example.com"
    response = client.post("/api/v1/auth/forgot-password", json={"email": nonexistent})

    assert response.status_code == 200
    assert "If an account exists" in response.json()["message"]

    # No email sent for nonexistent user
    assert email_service.last_sent_email is None


def test_forgot_password_identical_public_responses(client: TestClient, test_user):
    email, _, _, _ = test_user
    nonexistent = f"nobody-{uuid4().hex}@example.com"

    res_exist = client.post("/api/v1/auth/forgot-password", json={"email": email})
    password_reset_rate_limiter.reset()
    res_nonexist = client.post("/api/v1/auth/forgot-password", json={"email": nonexistent})

    assert res_exist.status_code == res_nonexist.status_code == 200
    assert res_exist.json() == res_nonexist.json()


# ==============================================================================
# 2. OTP VERIFICATION (/verify-otp)
# ==============================================================================

def test_verify_otp_valid_code(client: TestClient, test_user):
    email, _, auth_user_id, _ = test_user
    client.post("/api/v1/auth/forgot-password", json={"email": email})
    otp = email_service.last_sent_email["otp"]

    verify_res = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": otp})
    assert verify_res.status_code == 200
    body = verify_res.json()
    assert body["reset_token"]
    assert "confirmed" in body["message"].lower()

    # DB record is marked verified
    with SessionLocal() as session:
        challenge = session.query(PasswordResetOTP).filter(PasswordResetOTP.auth_user_id == auth_user_id).one()
        assert challenge.is_verified is True
        assert challenge.reset_token_hash is not None
        assert challenge.verified_at is not None


def test_verify_otp_invalid_code_decrements_attempts(client: TestClient, test_user):
    email, _, auth_user_id, _ = test_user
    client.post("/api/v1/auth/forgot-password", json={"email": email})

    verify_res = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": "000000"})
    assert verify_res.status_code == 400
    assert "4 attempts remaining" in _error_msg(verify_res)

    with SessionLocal() as session:
        challenge = session.query(PasswordResetOTP).filter(PasswordResetOTP.auth_user_id == auth_user_id).one()
        assert challenge.attempts == 1


def test_verify_otp_lockout_after_max_attempts(client: TestClient, test_user):
    email, _, auth_user_id, _ = test_user
    client.post("/api/v1/auth/forgot-password", json={"email": email})
    valid_otp = email_service.last_sent_email["otp"]

    # 4 invalid attempts
    for i in range(4):
        res = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": "111111"})
        assert res.status_code == 400
        assert f"{4 - i} attempt" in _error_msg(res)

    # 5th invalid attempt locks the challenge
    res5 = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": "111111"})
    assert res5.status_code == 400
    assert "locked" in _error_msg(res5).lower()

    # Even the valid code is now rejected
    res_after = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": valid_otp})
    assert res_after.status_code == 400
    assert "locked" in _error_msg(res_after).lower()


def test_verify_otp_expired_code(client: TestClient, test_user):
    email, _, auth_user_id, _ = test_user
    client.post("/api/v1/auth/forgot-password", json={"email": email})
    otp = email_service.last_sent_email["otp"]

    # Manually expire in DB
    with SessionLocal() as session:
        challenge = session.query(PasswordResetOTP).filter(PasswordResetOTP.auth_user_id == auth_user_id).one()
        challenge.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    res = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": otp})
    assert res.status_code == 400
    assert "expired" in _error_msg(res).lower()


def test_resend_otp_generates_fresh_challenge(client: TestClient, test_user):
    email, _, auth_user_id, _ = test_user
    client.post("/api/v1/auth/forgot-password", json={"email": email})
    otp1 = email_service.last_sent_email["otp"]

    password_reset_rate_limiter.reset()
    resend_res = client.post("/api/v1/auth/resend-otp", json={"email": email})
    assert resend_res.status_code == 200
    otp2 = email_service.last_sent_email["otp"]

    # Old code no longer works
    verify_old = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": otp1})
    if otp1 != otp2:
        assert verify_old.status_code == 400

    # New code works
    password_reset_rate_limiter.reset()
    verify_new = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": otp2})
    assert verify_new.status_code == 200
    assert verify_new.json()["reset_token"]


# ==============================================================================
# 3. PASSWORD RESET WITH VERIFIED TOKEN (/reset-password)
# ==============================================================================

def test_full_otp_password_reset_flow(client: TestClient, test_user):
    email, old_password, auth_user_id, _ = test_user

    # 1. Forgot password
    client.post("/api/v1/auth/forgot-password", json={"email": email})
    otp = email_service.last_sent_email["otp"]

    # 2. Verify OTP
    verify_res = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": otp})
    reset_token = verify_res.json()["reset_token"]

    # 3. Reset password
    new_password = "BrandNewSecurePassword456!"
    reset_res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )
    assert reset_res.status_code == 200
    assert "successfully reset" in reset_res.json()["message"]

    # Token is consumed in DB
    with SessionLocal() as session:
        challenge = session.query(PasswordResetOTP).filter(PasswordResetOTP.auth_user_id == auth_user_id).one()
        assert challenge.consumed_at is not None
        assert challenge.is_consumed is True

    # Login with old password fails
    login_old = client.post("/api/v1/auth/login", json={"email": email, "password": old_password})
    assert login_old.status_code == 401

    # Login with new password succeeds
    login_new = client.post("/api/v1/auth/login", json={"email": email, "password": new_password})
    assert login_new.status_code == 200
    assert login_new.json()["access_token"]


def test_reset_password_reused_token(client: TestClient, test_user):
    email, _, _, _ = test_user
    client.post("/api/v1/auth/forgot-password", json={"email": email})
    otp = email_service.last_sent_email["otp"]

    verify_res = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": otp})
    reset_token = verify_res.json()["reset_token"]

    first_reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "FirstNewPassword123!"},
    )
    assert first_reset.status_code == 200

    # Second attempt with same token must fail
    second_reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "SecondNewPassword123!"},
    )
    assert second_reset.status_code == 400
    assert "Invalid or expired" in _error_msg(second_reset)


def test_concurrent_token_consumption_is_atomic(client: TestClient, test_user):
    email, _, _, _ = test_user
    client.post("/api/v1/auth/forgot-password", json={"email": email})
    otp = email_service.last_sent_email["otp"]

    verify_res = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": otp})
    reset_token = verify_res.json()["reset_token"]

    def attempt_reset(pw: str):
        c = TestClient(app)
        return c.post("/api/v1/auth/reset-password", json={"token": reset_token, "new_password": pw})

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(attempt_reset, f"PasswordAttempt{i}12345!")
            for i in range(4)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    success_count = sum(1 for r in results if r.status_code == 200)
    failure_count = sum(1 for r in results if r.status_code == 400)

    assert success_count == 1
    assert failure_count == 3


def test_existing_sessions_invalidated_after_password_reset(client: TestClient, test_user):
    email, old_password, _, _ = test_user
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": old_password})
    old_jwt = login_res.json()["access_token"]

    # Verify old token works before reset
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_jwt}"}).status_code == 200

    # Complete password reset
    client.post("/api/v1/auth/forgot-password", json={"email": email})
    otp = email_service.last_sent_email["otp"]
    verify_res = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": otp})
    reset_token = verify_res.json()["reset_token"]

    client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "UpdatedPassword999!"},
    )

    # Old token must now be rejected because session_version changed
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_jwt}"})
    assert me_res.status_code == 401


def test_financial_user_and_data_remains_unchanged(client: TestClient, test_user):
    email, _, auth_user_id, financial_user_id = test_user

    client.post("/api/v1/auth/forgot-password", json={"email": email})
    otp = email_service.last_sent_email["otp"]
    verify_res = client.post("/api/v1/auth/verify-otp", json={"email": email, "otp": otp})
    reset_token = verify_res.json()["reset_token"]

    client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "NewFinancialPassword111!"},
    )

    with SessionLocal() as session:
        user = session.query(AuthUser).filter(AuthUser.id == auth_user_id).one()
        assert user.financial_user is not None
        assert user.financial_user.user_id == financial_user_id

        fin_user = session.query(User).filter(User.auth_user_id == auth_user_id).one()
        assert fin_user.user_id == financial_user_id


def test_forgot_password_rate_limiting_cooldown(client: TestClient, test_user):
    email, _, _, _ = test_user
    first = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert first.status_code == 200

    second = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert second.status_code == 429
    assert "Please wait" in _error_msg(second)


# ==============================================================================
# 4. EMAIL SERVICE & ERROR HANDLING
# ==============================================================================

def test_email_delivery_failure_handling(client: TestClient, test_user):
    email, _, _, _ = test_user

    with patch.object(
        email_service,
        "send_password_reset_otp",
        side_effect=EmailDeliveryError("Simulated delivery failure"),
    ):
        response = client.post("/api/v1/auth/forgot-password", json={"email": email})
        assert response.status_code == 503
        assert "Unable to deliver verification code" in _error_msg(response)


def test_email_service_provider_resolution_matrix():
    from app.core.config import Settings
    from app.services.email_service import EmailService

    # 1. Auto mode with no keys -> console
    svc_auto_console = EmailService(settings=Settings(email_delivery_provider="auto", resend_api_key="", smtp_host=""))
    with patch.object(svc_auto_console, "_write_console_banner") as mock_console:
        svc_auto_console.send_password_reset_otp("user@example.com", "123456")
        mock_console.assert_called_once()

    # 2. Auto mode with Resend key -> resend
    svc_auto_resend = EmailService(settings=Settings(email_delivery_provider="auto", resend_api_key="re_test_key", smtp_host=""))
    with patch.object(svc_auto_resend, "_send_via_resend") as mock_resend:
        svc_auto_resend.send_password_reset_otp("user@example.com", "123456")
        mock_resend.assert_called_once()

    # 3. Auto mode with SMTP host -> smtp
    svc_auto_smtp = EmailService(settings=Settings(email_delivery_provider="auto", resend_api_key="", smtp_host="smtp.gmail.com"))
    with patch.object(svc_auto_smtp, "_send_via_smtp") as mock_smtp:
        svc_auto_smtp.send_password_reset_otp("user@example.com", "123456")
        mock_smtp.assert_called_once()


def test_email_service_explicit_provider_error_handling():
    from app.core.config import Settings
    from app.services.email_service import EmailService

    # Resend selected without key
    svc_resend_missing = EmailService(settings=Settings(email_delivery_provider="resend", resend_api_key=""))
    with pytest.raises(EmailDeliveryError, match="Resend API key is not configured"):
        svc_resend_missing.send_password_reset_otp("user@example.com", "123456")

    # SMTP selected without host
    svc_smtp_missing = EmailService(settings=Settings(email_delivery_provider="smtp", smtp_host=""))
    with pytest.raises(EmailDeliveryError, match="SMTP host is not configured"):
        svc_smtp_missing.send_password_reset_otp("user@example.com", "123456")


def test_explicit_console_mode_does_not_contact_resend():
    from app.core.config import Settings
    from app.services.email_service import EmailService

    settings = Settings(
        email_delivery_provider="console",
        resend_api_key="re_test_dummy_key_12345",
        environment="development",
    )
    svc = EmailService(settings=settings)

    with patch.object(svc, "_send_via_resend") as mock_resend, \
         patch.object(svc, "_write_console_banner") as mock_console:
        svc.send_password_reset_otp("user@example.com", "654321")
        mock_resend.assert_not_called()
        mock_console.assert_called_once()


def test_console_mode_terminal_output_banner(capsys):
    from app.core.config import Settings
    from app.services.email_service import EmailService

    settings = Settings(
        email_delivery_provider="console",
        frontend_base_url="http://localhost:5173",
        environment="development",
    )
    svc = EmailService(settings=settings)
    svc.send_password_reset_otp("testdev@example.com", "584920")

    captured = capsys.readouterr()
    assert "[FINSIGHT LOCAL DEV OTP DISPATCH]" in captured.err
    assert "To: testdev@example.com" in captured.err
    assert "Verification Code (OTP): 584920" in captured.err


def test_production_environment_rejects_console_mode():
    from pydantic import ValidationError
    from app.core.config import Settings
    from app.services.email_service import EmailService

    with pytest.raises(ValidationError, match="EMAIL_DELIVERY_PROVIDER cannot be 'console' in production"):
        Settings(
            environment="production",
            email_delivery_provider="console",
            auth_jwt_secret="a" * 32,
        )

    prod_settings = Settings(
        environment="production",
        email_delivery_provider="auto",
        resend_api_key="",
        smtp_host="",
        auth_jwt_secret="a" * 32,
    )
    prod_svc = EmailService(settings=prod_settings)
    with pytest.raises(EmailDeliveryError, match="No external email provider configured for production environment"):
        prod_svc.send_password_reset_otp("user@example.com", "123456")


def test_resend_403_raises_503_and_is_not_treated_as_success(client: TestClient, test_user):
    email, _, _, _ = test_user

    import httpx
    mock_resp = httpx.Response(
        status_code=403,
        json={"message": "You can only send testing emails to your own email address", "statusCode": 403},
        request=httpx.Request("POST", "https://api.resend.com/emails"),
    )

    with patch("httpx.Client.post", return_value=mock_resp), \
         patch.object(email_service.settings, "email_delivery_provider", "resend"), \
         patch.object(email_service.settings, "resend_api_key", "re_dummy_key"):
        response = client.post("/api/v1/auth/forgot-password", json={"email": email})
        assert response.status_code == 503
        assert "Unable to deliver verification code" in _error_msg(response)


# ==============================================================================
# 5. LEGACY RESET TOKEN BACKWARD COMPATIBILITY
# ==============================================================================

def test_legacy_reset_token_backward_compatibility(client: TestClient, test_user):
    email, old_password, auth_user_id, _ = test_user

    # Manually create legacy PasswordResetToken
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with SessionLocal() as session:
        legacy = PasswordResetToken(
            auth_user_id=auth_user_id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        session.add(legacy)
        session.commit()

    # Reset password with legacy token
    new_pw = "LegacyTokenResetPassword888!"
    res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": new_pw},
    )
    assert res.status_code == 200
    assert "successfully reset" in res.json()["message"]

    # Verify new password works
    login_new = client.post("/api/v1/auth/login", json={"email": email, "password": new_pw})
    assert login_new.status_code == 200
