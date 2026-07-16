from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from tests.conftest import auth_headers_for, create_test_user


def test_role_access_allowed_for_police_violations(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session,
        email="police@example.com",
        role=UserRole.POLICE,
    )

    response = client.get("/api/v1/violations", headers=auth_headers_for(user))

    assert response.status_code == 200


def test_role_access_denied_for_analyst_violations(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session,
        email="rbac-analyst@example.com",
        role=UserRole.ANALYST,
    )

    response = client.get("/api/v1/violations", headers=auth_headers_for(user))

    assert response.status_code == 403
