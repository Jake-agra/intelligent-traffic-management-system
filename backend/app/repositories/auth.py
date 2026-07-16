import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import RefreshToken
from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_refresh_token_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
    return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))


def add_refresh_token(db: Session, refresh_token: RefreshToken) -> RefreshToken:
    db.add(refresh_token)
    db.flush()
    return refresh_token
