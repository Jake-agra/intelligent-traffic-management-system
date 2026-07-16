from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import RefreshToken
from app.models.user import User
from app.repositories import auth as auth_repository
from app.schemas.auth import TokenPairResponse
from app.security.passwords import verify_password
from app.security.tokens import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
)


class AuthenticationError(Exception):
    pass


class RefreshTokenError(Exception):
    pass


class LoginRateLimiter:
    """Small in-process hook ready to be swapped for Redis-backed limits."""

    def is_allowed(self, email: str) -> bool:
        return True

    def record_failure(self, email: str) -> None:
        return None

    def record_success(self, email: str) -> None:
        return None


login_rate_limiter = LoginRateLimiter()


def login_user(db: Session, *, email: str, password: str) -> TokenPairResponse:
    normalized_email = email.lower()
    if not login_rate_limiter.is_allowed(normalized_email):
        raise AuthenticationError("Too many login attempts.")

    user = auth_repository.get_user_by_email(db, normalized_email)
    if user is None or not verify_password(password, user.password_hash):
        login_rate_limiter.record_failure(normalized_email)
        raise AuthenticationError("Invalid email or password.")

    if not user.is_active:
        login_rate_limiter.record_failure(normalized_email)
        raise AuthenticationError("Inactive user.")

    login_rate_limiter.record_success(normalized_email)
    return issue_token_pair(db, user=user)


def issue_token_pair(db: Session, *, user: User) -> TokenPairResponse:
    settings = get_settings()
    access_token = create_access_token(user_id=user.id, role=user.role)
    refresh_token = create_refresh_token()
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    auth_repository.add_refresh_token(db, refresh_record)
    db.commit()
    db.refresh(user)
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=user,
    )


def refresh_token_pair(db: Session, *, refresh_token: str) -> TokenPairResponse:
    record = _get_valid_refresh_record(db, refresh_token)
    user = record.user
    if not user.is_active:
        raise RefreshTokenError("Inactive user.")

    token_pair = issue_token_pair(db, user=user)
    replacement = auth_repository.get_refresh_token_by_hash(
        db,
        hash_refresh_token(token_pair.refresh_token),
    )
    record.revoked_at = datetime.now(UTC)
    record.replaced_by_token_id = replacement.id if replacement else None
    db.add(record)
    db.commit()
    return token_pair


def revoke_refresh_token(db: Session, *, refresh_token: str) -> None:
    record = _get_valid_refresh_record(db, refresh_token)
    record.revoked_at = datetime.now(UTC)
    db.add(record)
    db.commit()


def _get_valid_refresh_record(db: Session, refresh_token: str) -> RefreshToken:
    token_hash = hash_refresh_token(refresh_token)
    record = auth_repository.get_refresh_token_by_hash(db, token_hash)
    now = datetime.now(UTC)
    if record is None:
        raise RefreshTokenError("Invalid refresh token.")

    expires_at = _ensure_timezone(record.expires_at)
    if record.revoked_at is not None or expires_at <= now:
        raise RefreshTokenError("Invalid refresh token.")
    return record


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
