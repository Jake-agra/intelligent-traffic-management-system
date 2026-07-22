from collections.abc import Generator
import asyncio
import inspect
import json
import os
from urllib.parse import urlencode, urlsplit

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


os.environ["ENVIRONMENT"] = "test"
os.environ["MQTT_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.api.deps import get_db_session
from app.main import app
from app.models.enums import UserRole
from app.models import Base
from app.models.user import User
from app.security.passwords import hash_password
from app.security.tokens import create_access_token


class SameThreadPortal:
    def call(self, func, *args, **kwargs):
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            return asyncio.run(result)
        return result


class ASGIResponse:
    def __init__(
        self,
        *,
        status_code: int,
        headers: list[tuple[bytes, bytes]],
        content: bytes,
    ) -> None:
        self.status_code = status_code
        self.headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in headers
        }
        self.content = content

    def json(self):
        return json.loads(self.content.decode("utf-8"))


class SameThreadASGIClient:
    def __init__(self, app) -> None:
        self.app = app
        self.portal = SameThreadPortal()

    def get(self, url: str, **kwargs) -> ASGIResponse:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> ASGIResponse:
        return self.request("POST", url, **kwargs)

    def request(self, method: str, url: str, **kwargs) -> ASGIResponse:
        async def run_request() -> ASGIResponse:
            return await self._request(method, url, **kwargs)

        return asyncio.run(run_request())

    async def _request(self, method: str, url: str, **kwargs) -> ASGIResponse:
        parsed_url = urlsplit(url)
        path = parsed_url.path or "/"
        query = parsed_url.query
        params = kwargs.pop("params", None)
        if params:
            encoded_params = urlencode(params, doseq=True)
            query = f"{query}&{encoded_params}" if query else encoded_params

        body = b""
        request_headers: list[tuple[bytes, bytes]] = [(b"host", b"testserver")]
        headers = kwargs.pop("headers", None) or {}
        if "json" in kwargs:
            body = json.dumps(kwargs.pop("json")).encode("utf-8")
            request_headers.append((b"content-type", b"application/json"))
        for key, value in headers.items():
            request_headers.append(
                (key.lower().encode("latin-1"), value.encode("latin-1"))
            )

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": query.encode("ascii"),
            "headers": request_headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }

        request_sent = False
        response_started: dict[str, object] = {}
        response_body = bytearray()

        async def receive() -> dict[str, object]:
            nonlocal request_sent
            if request_sent:
                return {"type": "http.disconnect"}
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict[str, object]) -> None:
            if message["type"] == "http.response.start":
                response_started.update(message)
            elif message["type"] == "http.response.body":
                response_body.extend(message.get("body", b""))

        await self.app(scope, receive, send)
        return ASGIResponse(
            status_code=int(response_started["status"]),
            headers=response_started.get("headers", []),
            content=bytes(response_body),
        )


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
def client(db_session: Session) -> Generator[SameThreadASGIClient, None, None]:
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield SameThreadASGIClient(app)
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
