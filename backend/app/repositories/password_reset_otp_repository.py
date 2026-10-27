from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.database.models.password_reset_otp import PasswordResetOTP


class PasswordResetOTPRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        auth_user_id: int,
        otp_hash: str,
        expires_at: datetime,
        max_attempts: int = 5,
    ) -> PasswordResetOTP:
        challenge = PasswordResetOTP(
            auth_user_id=auth_user_id,
            otp_hash=otp_hash,
            expires_at=expires_at,
            max_attempts=max_attempts,
        )
        self.session.add(challenge)
        self.session.flush()
        return challenge

    def get_latest_active_challenge(self, auth_user_id: int) -> PasswordResetOTP | None:
        now = datetime.now(timezone.utc)
        return self.session.execute(
            select(PasswordResetOTP)
            .options(selectinload(PasswordResetOTP.auth_user))
            .where(
                PasswordResetOTP.auth_user_id == auth_user_id,
                PasswordResetOTP.consumed_at.is_(None),
                PasswordResetOTP.verified_at.is_(None),
                PasswordResetOTP.expires_at > now,
            )
            .order_by(PasswordResetOTP.id.desc())
        ).scalars().first()

    def increment_attempts(self, otp_id: int) -> int:
        self.session.execute(
            update(PasswordResetOTP)
            .where(PasswordResetOTP.id == otp_id)
            .values(attempts=PasswordResetOTP.attempts + 1)
        )
        self.session.commit()
        refreshed = self.session.execute(
            select(PasswordResetOTP.attempts).where(PasswordResetOTP.id == otp_id)
        ).scalar_one_or_none()
        return refreshed or 0

    def mark_verified(self, otp_id: int, reset_token_hash: str, expires_at: datetime) -> bool:
        now = datetime.now(timezone.utc)
        result = self.session.execute(
            update(PasswordResetOTP)
            .where(
                PasswordResetOTP.id == otp_id,
                PasswordResetOTP.verified_at.is_(None),
                PasswordResetOTP.consumed_at.is_(None),
                PasswordResetOTP.expires_at > now,
            )
            .values(
                verified_at=now,
                reset_token_hash=reset_token_hash,
                expires_at=expires_at,
            )
        )
        self.session.commit()
        return result.rowcount > 0

    def consume_reset_token_atomically(self, reset_token_hash: str) -> PasswordResetOTP | None:
        now = datetime.now(timezone.utc)
        result = self.session.execute(
            update(PasswordResetOTP)
            .where(
                PasswordResetOTP.reset_token_hash == reset_token_hash,
                PasswordResetOTP.verified_at.is_not(None),
                PasswordResetOTP.consumed_at.is_(None),
                PasswordResetOTP.expires_at > now,
            )
            .values(consumed_at=now)
        )
        self.session.commit()
        if result.rowcount == 0:
            return None

        return self.session.execute(
            select(PasswordResetOTP)
            .options(selectinload(PasswordResetOTP.auth_user))
            .where(PasswordResetOTP.reset_token_hash == reset_token_hash)
        ).scalar_one_or_none()

    def invalidate_active_challenges_for_user(self, auth_user_id: int) -> int:
        now = datetime.now(timezone.utc)
        result = self.session.execute(
            update(PasswordResetOTP)
            .where(
                PasswordResetOTP.auth_user_id == auth_user_id,
                PasswordResetOTP.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        return result.rowcount
