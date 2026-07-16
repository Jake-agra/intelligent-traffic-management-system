from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.main import app
from app.models.enums import UserRole
from app.models import Base
from app.models.user import User
from app.security.passwords import hash_password
from app.security.tokens import create_access_token


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    with TestingSessionLocal() as session:
        yield session

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_test_user(
    db_session: Session,
    *,
    email: str = "operator@example.com",
    password: str = "correct-password",
    role: UserRole = UserRole.ANALYST,
    is_active: bool = True,
) -> User:
    user = User(
        email=email.lower(),
        display_name="Test User",
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_headers_for(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def analyst_headers(db_session: Session) -> dict[str, str]:
    user = create_test_user(
        db_session,
        email="analyst@example.com",
        role=UserRole.ANALYST,
    )
    return auth_headers_for(user)


@pytest.fixture
def admin_headers(db_session: Session) -> dict[str, str]:
    user = create_test_user(
        db_session,
        email="admin@example.com",
        role=UserRole.ADMIN,
    )
    return auth_headers_for(user)
