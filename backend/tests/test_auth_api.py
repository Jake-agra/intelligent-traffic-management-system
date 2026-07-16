from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from tests.conftest import auth_headers_for, create_test_user


def test_valid_login_returns_token_pair_and_user_profile(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session,
        email="login@example.com",
        password="correct-password",
        role=UserRole.POLICE,
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "correct-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == "login@example.com"
    assert body["user"]["role"] == UserRole.POLICE.value


def test_invalid_password_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(db_session, email="invalid@example.com")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "invalid@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_inactive_user_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session,
        email="inactive@example.com",
        is_active=False,
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "correct-password"},
    )

    assert response.status_code == 401


def test_me_returns_current_user_profile(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session,
        email="me@example.com",
        role=UserRole.EMERGENCY_RESPONDER,
    )

    response = client.get("/api/v1/auth/me", headers=auth_headers_for(user))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["role"] == UserRole.EMERGENCY_RESPONDER.value


def test_refresh_token_rotation_revokes_old_refresh_token(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(db_session, email="refresh@example.com")
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "correct-password"},
    )
    old_refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert refresh_response.status_code == 200
    new_refresh_token = refresh_response.json()["refresh_token"]
    assert new_refresh_token != old_refresh_token

    revoked_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert revoked_response.status_code == 401


def test_revoked_refresh_token_is_rejected_after_logout(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(db_session, email="logout-refresh@example.com")
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "logout-refresh@example.com", "password": "correct-password"},
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert logout_response.status_code == 200
    assert logout_response.json() == {"revoked": True}
    assert refresh_response.status_code == 401


def test_logout_revokes_refresh_token(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(db_session, email="logout@example.com")
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "correct-password"},
    )

    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": login_response.json()["refresh_token"]},
    )

    assert response.status_code == 200
    assert response.json() == {"revoked": True}


def test_missing_token_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
