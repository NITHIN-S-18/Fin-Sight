from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.database.connection import SessionLocal
from app.database.models.auth_user import AuthUser
from app.database.models.user import User
from app.repositories.auth_user_repository import AuthUserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    encode = base64.urlsafe_b64encode
    return f"scrypt${encode(salt).decode()}${encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt_value, digest_value = encoded.split("$", 2)
        if scheme != "scrypt":
            return False
        decode = base64.urlsafe_b64decode
        expected = decode(digest_value)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=decode(salt_value), n=16384, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, settings: Settings, session_version: int = 0) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.auth_access_token_expire_minutes)
    return jwt.encode(
        {"sub": str(user_id), "exp": expires_at, "sv": session_version},
        settings.auth_jwt_secret,
        algorithm=settings.auth_jwt_algorithm,
    )


def get_current_auth_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.auth_jwt_secret,
            algorithms=[settings.auth_jwt_algorithm],
        )
        user_id = int(payload.get("sub", ""))
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise unauthorized from None

    with SessionLocal() as session:
        auth_user = AuthUserRepository(session).get_by_id(user_id)
        if auth_user is None:
            raise unauthorized
        if payload.get("sv") != auth_user.session_version:
            raise unauthorized
        if auth_user.financial_user is None:
            auth_user.financial_user = User(
                user_id=f"AUTH{auth_user.id:08d}",
                auth_user_id=auth_user.id,
            )
            session.commit()
            session.refresh(auth_user)
        session.expunge(auth_user)
        return auth_user


def get_current_financial_user(
    auth_user: AuthUser = Depends(get_current_auth_user),
) -> User:
    if auth_user.financial_user is not None:
        return auth_user.financial_user

    with SessionLocal() as session:
        user = session.query(User).filter(User.auth_user_id == auth_user.id).one_or_none()
        if user is None:
            user = User(
                user_id=f"AUTH{auth_user.id:08d}",
                auth_user_id=auth_user.id,
            )
            session.add(user)
            session.commit()
        session.expunge(user)
        return user


def require_financial_user(user_id: str, current_user: User) -> str:
    if user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another user's financial data",
        )
    return current_user.user_id