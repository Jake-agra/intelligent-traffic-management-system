import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db_session, require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import traffic_operations
from app.schemas.operations import (
    SignalModeRequest,
    SignalModeResponse,
    SignalOverrideRequest,
    SignalOverrideResponse,
)
from app.schemas.traffic_operations import (
    IntersectionDetailResponse,
    IntersectionLiveResponse,
    IntersectionSummaryResponse,
)
from app.services import operations


router = APIRouter(prefix="/intersections", tags=["traffic operations"])


@router.get("", response_model=list[IntersectionSummaryResponse])
def list_intersections(
    _current_user=Depends(get_active_user),
    db: Session = Depends(get_db_session),
) -> list[IntersectionSummaryResponse]:
    return list(traffic_operations.list_intersections(db))


@router.get("/{intersection_id}", response_model=IntersectionDetailResponse)
def get_intersection(
    intersection_id: uuid.UUID,
    _current_user=Depends(get_active_user),
    db: Session = Depends(get_db_session),
) -> IntersectionDetailResponse:
    intersection = traffic_operations.get_intersection(db, intersection_id)
    if intersection is None:
        raise HTTPException(status_code=404, detail="Intersection not found.")
    return intersection


@router.get("/{intersection_id}/live", response_model=IntersectionLiveResponse)
def get_intersection_live_state(
    intersection_id: uuid.UUID,
    _current_user=Depends(get_active_user),
    db: Session = Depends(get_db_session),
) -> IntersectionLiveResponse:
    live_state = traffic_operations.get_intersection_live_state(db, intersection_id)
    if live_state is None:
        raise HTTPException(status_code=404, detail="Intersection not found.")
    return live_state


@router.post("/{intersection_id}/signal-mode", response_model=SignalModeResponse)
async def change_signal_mode(
    intersection_id: uuid.UUID,
    request: SignalModeRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db_session),
) -> SignalModeResponse:
    return await operations.change_signal_mode(
        db,
        intersection_id=intersection_id,
        mode=request.mode,
        reason=request.reason,
        user=current_user,
    )


@router.post("/{intersection_id}/signal-override", response_model=SignalOverrideResponse)
async def override_signal(
    intersection_id: uuid.UUID,
    request: SignalOverrideRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db_session),
) -> SignalOverrideResponse:
    return await operations.override_signal(
        db,
        intersection_id=intersection_id,
        lane_id=request.lane_id,
        requested_color=request.requested_color,
        duration_seconds=request.duration_seconds,
        reason=request.reason,
        user=current_user,
    )
