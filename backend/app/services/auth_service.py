from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.database.connection import SessionLocal
from app.database.models.user import User
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.password_reset_token_repository import PasswordResetTokenRepository
from app.repositories.password_reset_otp_repository import PasswordResetOTPRepository
from app.schemas.auth import (
    AuthUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.services.email_service import EmailDeliveryError, EmailService, get_email_service
from app.services.rate_limiter import password_reset_rate_limiter

logger = logging.getLogger("finsight.auth")


class AuthService:
    def __init__(
        self,
        email_service: EmailService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.email_service = email_service or get_email_service()
        self.settings = settings or get_settings()

    def register(self, request: RegisterRequest) -> AuthUserResponse:
        with SessionLocal() as session:
            repository = AuthUserRepository(session)
            if repository.get_by_email(request.email) is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
            try:
                user = repository.create(request.email, hash_password(request.password))
                user.display_name = request.display_name.strip() if request.display_name else None
                session.flush()
                financial_user = User(
                    user_id=f"AUTH{user.id:08d}",
                )
                user.financial_user = financial_user
                session.add(financial_user)
                session.commit()
            except IntegrityError:
                session.rollback()
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from None
            return AuthUserResponse.model_validate(user)

    def login(self, request: LoginRequest, settings: Settings) -> TokenResponse:
        with SessionLocal() as session:
            user = AuthUserRepository(session).get_by_email(request.email)
            if user is None or not verify_password(request.password, user.password_hash):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
            return TokenResponse(access_token=create_access_token(user.id, settings, user.session_version))

    def update_profile(self, user: User, request: ProfileUpdateRequest) -> AuthUserResponse:
        with SessionLocal() as session:
            auth_user = AuthUserRepository(session).get_by_id(user.auth_user_id)
            if auth_user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication account not found")
            auth_user.display_name = request.display_name.strip()
            if not auth_user.display_name:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Display name cannot be empty")
            session.commit()
            session.refresh(auth_user)
            return AuthUserResponse.model_validate(auth_user)

    def change_password(self, user: User, request: PasswordChangeRequest) -> None:
        with SessionLocal() as session:
            auth_user = AuthUserRepository(session).get_by_id(user.auth_user_id)
            if auth_user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication account not found")
            if not verify_password(request.current_password, auth_user.password_hash):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
            if request.current_password == request.new_password:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password must differ from the current password")
            auth_user.password_hash = hash_password(request.new_password)
            auth_user.session_version += 1
            session.commit()

    def request_password_reset(self, request: ForgotPasswordRequest, client_ip: str = "") -> MessageResponse:
        allowed, reason = password_reset_rate_limiter.check_and_record(request.email, client_ip)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=reason or "Too many requests. Please try again later.",
            )

        public_msg = (
            "If an account exists for this email address, a 6-digit verification code has been sent."
        )

        with SessionLocal() as session:
            auth_repo = AuthUserRepository(session)
            user = auth_repo.get_by_email(request.email)
            if user is None:
                return MessageResponse(message=public_msg)

            otp = f"{secrets.randbelow(1_000_000):06d}"
            salt = secrets.token_hex(16)
            otp_hash = f"{salt}${hashlib.sha256(f'{otp}:{salt}'.encode('utf-8')).hexdigest()}"
            expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=self.settings.auth_password_reset_otp_expire_minutes
            )

            otp_repo = PasswordResetOTPRepository(session)
            otp_repo.invalidate_active_challenges_for_user(user.id)
            otp_repo.create(auth_user_id=user.id, otp_hash=otp_hash, expires_at=expires_at, max_attempts=5)

            # Also maintain legacy token for backwards-compatibility with link tests if needed
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            token_repo = PasswordResetTokenRepository(session)
            token_repo.invalidate_active_tokens_for_user(user.id)
            token_repo.create(auth_user_id=user.id, token_hash=token_hash, expires_at=expires_at)
            session.commit()

        try:
            self.email_service.send_password_reset_otp(user.email, otp)
        except EmailDeliveryError as exc:
            logger.error("Failed to deliver password reset OTP for %s: %s", user.email, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to deliver verification code. Please try again later.",
            ) from exc

        return MessageResponse(message=public_msg)

    def verify_otp(self, request: VerifyOtpRequest) -> VerifyOtpResponse:
        with SessionLocal() as session:
            auth_repo = AuthUserRepository(session)
            user = auth_repo.get_by_email(request.email)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired verification code.",
                )

            otp_repo = PasswordResetOTPRepository(session)
            challenge = otp_repo.get_latest_active_challenge(user.id)
            if challenge is None or challenge.is_expired:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired verification code. Please request a new code.",
                )

            if challenge.is_attempts_exceeded:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Too many failed attempts. This code has been locked. Please request a new code.",
                )

            salt, stored_hash = challenge.otp_hash.split("$", 1)
            candidate_hash = hashlib.sha256(f"{request.otp.strip()}:{salt}".encode("utf-8")).hexdigest()
            if not secrets.compare_digest(stored_hash, candidate_hash):
                new_attempts = otp_repo.increment_attempts(challenge.id)
                remaining = max(0, challenge.max_attempts - new_attempts)
                if remaining == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Too many failed attempts. This code has been locked. Please request a new code.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
                )

            raw_reset_token = secrets.token_urlsafe(32)
            reset_token_hash = hashlib.sha256(raw_reset_token.encode("utf-8")).hexdigest()
            reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=15)

            verified = otp_repo.mark_verified(challenge.id, reset_token_hash, reset_token_expires)
            if not verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Verification could not be completed. Please request a new code.",
                )

            return VerifyOtpResponse(
                reset_token=raw_reset_token,
                message="Verification code confirmed. You can now set a new password.",
            )

    def resend_otp(self, request: ForgotPasswordRequest, client_ip: str = "") -> MessageResponse:
        return self.request_password_reset(request, client_ip=client_ip)

    def reset_password(self, request: ResetPasswordRequest) -> MessageResponse:
        token_hash = hashlib.sha256(request.token.encode("utf-8")).hexdigest()

        with SessionLocal() as session:
            otp_repo = PasswordResetOTPRepository(session)
            otp_challenge = otp_repo.consume_reset_token_atomically(token_hash)
            auth_user = None

            if otp_challenge is not None and otp_challenge.auth_user is not None:
                auth_user = otp_challenge.auth_user
            else:
                token_repo = PasswordResetTokenRepository(session)
                consumed = token_repo.consume_token_atomically(token_hash)
                if consumed:
                    token_record = token_repo.get_by_hash(token_hash)
                    if token_record and token_record.auth_user:
                        auth_user = token_record.auth_user

            if auth_user is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired password reset token",
                )

            auth_user.password_hash = hash_password(request.new_password)
            auth_user.session_version += 1
            otp_repo.invalidate_active_challenges_for_user(auth_user.id)
            PasswordResetTokenRepository(session).invalidate_active_tokens_for_user(auth_user.id)
            session.commit()

        return MessageResponse(
            message="Your password has been successfully reset. You can now sign in with your new password."
        )

    async def upload_avatar(self, user: User, file: UploadFile) -> AuthUserResponse:
        import uuid
        from pathlib import Path

        # Enforce max 5 MB size
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Image file is empty")
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Profile photo must be under 5 MB")

        # Validate magic numbers
        if content.startswith(b"\xff\xd8\xff"):
            ext = ".jpg"
        elif content.startswith(b"\x89PNG\r\n\x1a\n"):
            ext = ".png"
        elif content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP":
            ext = ".webp"
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid image format. Supported formats: JPEG, PNG, WebP",
            )

        base_dir = Path(__file__).resolve().parent.parent.parent
        avatars_dir = base_dir / "uploads" / "avatars"
        avatars_dir.mkdir(parents=True, exist_ok=True)

        with SessionLocal() as session:
            auth_user = AuthUserRepository(session).get_by_id(user.auth_user_id)
            if auth_user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication account not found")

            # Remove existing file if present
            if auth_user.avatar_url and "/api/v1/auth/avatar/" in auth_user.avatar_url:
                old_name = auth_user.avatar_url.split("/api/v1/auth/avatar/")[-1]
                old_path = avatars_dir / old_name
                if old_path.is_file():
                    try:
                        old_path.unlink()
                    except Exception:
                        pass

            filename = f"avatar_{auth_user.id}_{uuid.uuid4().hex[:12]}{ext}"
            file_path = avatars_dir / filename
            file_path.write_bytes(content)

            auth_user.avatar_url = f"/api/v1/auth/avatar/{filename}"
            session.commit()
            session.refresh(auth_user)
            return AuthUserResponse.model_validate(auth_user)

    def delete_avatar(self, user: User) -> AuthUserResponse:
        from pathlib import Path

        base_dir = Path(__file__).resolve().parent.parent.parent
        avatars_dir = base_dir / "uploads" / "avatars"

        with SessionLocal() as session:
            auth_user = AuthUserRepository(session).get_by_id(user.auth_user_id)
            if auth_user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication account not found")

            if auth_user.avatar_url and "/api/v1/auth/avatar/" in auth_user.avatar_url:
                old_name = auth_user.avatar_url.split("/api/v1/auth/avatar/")[-1]
                old_path = avatars_dir / old_name
                if old_path.is_file():
                    try:
                        old_path.unlink()
                    except Exception:
                        pass

            auth_user.avatar_url = None
            session.commit()
            session.refresh(auth_user)
            return AuthUserResponse.model_validate(auth_user)

    def get_avatar_file(self, filename: str):
        import re
        from pathlib import Path

        if not re.match(r"^avatar_\d+_[a-zA-Z0-9]+\.(jpg|jpeg|png|webp)$", filename):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename format")

        base_dir = Path(__file__).resolve().parent.parent.parent
        file_path = base_dir / "uploads" / "avatars" / filename
        if not file_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar image not found")
        return file_path


def get_auth_service(
    email_service: EmailService = Depends(get_email_service),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(email_service=email_service, settings=settings)
