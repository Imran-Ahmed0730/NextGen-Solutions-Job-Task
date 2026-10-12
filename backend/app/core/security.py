from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.auth.models import RefreshToken, User

settings = get_settings()
password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)
_dummy_password_hash = password_hash.hash("invalid-login-placeholder")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user: User, session_id: int) -> str:
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "sid": session_id,
        "exp": int(expires_at.timestamp()),
        "iat": int(issued_at.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> tuple[str, datetime]:
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    return token, expires_at


def authenticate_user(db: Session, username: str, password: str) -> User:
    statement = select(User).where(
        or_(User.username == username, User.email == username, User.mobile == username)
    )
    user = db.scalar(statement)
    if user is None:
        password_hash.verify(password, _dummy_password_hash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        password_hash.verify(password, _dummy_password_hash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    locked_until = user.locked_until
    if locked_until:
        if _as_utc(locked_until) > datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is locked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user.failed_attempts = 0
        setattr(user, "locked_until", None)

    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.login_max_failed_attempts:
            user.locked_until = datetime.now(UTC) + timedelta(
                minutes=settings.login_lockout_minutes
            )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.failed_attempts = 0
    setattr(user, "locked_until", None)
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return user


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
    request: Request | None = None,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload["sub"])
        session_id = int(payload["sid"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    refresh_session = db.get(RefreshToken, session_id)
    if (
        refresh_session is None
        or refresh_session.user_id != user.id
        or refresh_session.revoked_at is not None
        or _as_utc(refresh_session.expires_at) <= datetime.now(UTC)
    ):
        raise unauthorized
    if request is not None:
        request.state.auth_session_id = session_id
    if user.locked_until and _as_utc(user.locked_until) > datetime.now(UTC):
        raise unauthorized
    return user


def has_permission(user: User, permission_code: str) -> bool:
    return any(
        role.is_active
        and any(permission.code == permission_code for permission in role.permissions)
        for role in user.roles
    )


def require_permission(permission_code: str) -> Callable[..., User]:
    from fastapi import Depends

    def dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        db: Session = Depends(get_db),
    ) -> User:
        user = get_current_user(credentials, db, request)
        if not has_permission(user, permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "PERMISSION_DENIED", "permission": permission_code},
            )
        return user

    return dependency
