from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db_session
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    TokenPairResponse,
    UserProfile,
)
from app.services.auth import (
    AuthenticationError,
    RefreshTokenError,
    login_user,
    refresh_token_pair,
    revoke_refresh_token,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPairResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db_session),
) -> TokenPairResponse:
    try:
        return login_user(db, email=request.email, password=request.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(
    request: RefreshRequest,
    db: Session = Depends(get_db_session),
) -> TokenPairResponse:
    try:
        return refresh_token_pair(db, refresh_token=request.refresh_token)
    except RefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: LogoutRequest,
    db: Session = Depends(get_db_session),
) -> LogoutResponse:
    try:
        revoke_refresh_token(db, refresh_token=request.refresh_token)
    except RefreshTokenError:
        return LogoutResponse(revoked=True)
    return LogoutResponse(revoked=True)


@router.get("/me", response_model=UserProfile)
def me(current_user: User = Depends(get_active_user)) -> User:
    return current_user
