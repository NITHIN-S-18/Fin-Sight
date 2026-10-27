from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.database.models.password_reset_token import PasswordResetToken


class PasswordResetTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, auth_user_id: int, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        token = PasswordResetToken(
            auth_user_id=auth_user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(token)
        self.session.flush()
        return token

    def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return self.session.execute(
            select(PasswordResetToken)
            .options(selectinload(PasswordResetToken.auth_user))
            .where(PasswordResetToken.token_hash == token_hash)
        ).scalar_one_or_none()

    def consume_token_atomically(self, token_hash: str) -> bool:
        now = datetime.now(timezone.utc)
        result = self.session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.consumed_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
            .values(consumed_at=now)
        )
        return result.rowcount > 0

    def invalidate_active_tokens_for_user(self, auth_user_id: int) -> int:
        now = datetime.now(timezone.utc)
        result = self.session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.auth_user_id == auth_user_id,
                PasswordResetToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        return result.rowcount

    def count_recent_tokens_for_user(self, auth_user_id: int, since: datetime) -> int:
        return self.session.execute(
            select(func.count(PasswordResetToken.id)).where(
                PasswordResetToken.auth_user_id == auth_user_id,
                PasswordResetToken.created_at >= since,
            )
        ).scalar_one() or 0
