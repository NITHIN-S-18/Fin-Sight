from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models.auth_user import AuthUser


class AuthUserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_email(self, email: str) -> AuthUser | None:
        return self.session.execute(
            select(AuthUser).where(AuthUser.email == email)
        ).scalar_one_or_none()

    def get_by_id(self, user_id: int) -> AuthUser | None:
        return self.session.execute(
            select(AuthUser).options(selectinload(AuthUser.financial_user)).where(AuthUser.id == user_id)
        ).scalar_one_or_none()

    def create(self, email: str, password_hash: str) -> AuthUser:
        user = AuthUser(email=email, password_hash=password_hash)
        self.session.add(user)
        self.session.flush()
        return user