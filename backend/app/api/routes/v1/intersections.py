import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.repositories import traffic_operations
from app.schemas.traffic_operations import (
    IntersectionDetailResponse,
    IntersectionLiveResponse,
    IntersectionSummaryResponse,
)


router = APIRouter(prefix="/intersections", tags=["traffic operations"])


@router.get("", response_model=list[IntersectionSummaryResponse])
def list_intersections(
    db: Session = Depends(get_db_session),
) -> list[IntersectionSummaryResponse]:
    return list(traffic_operations.list_intersections(db))


@router.get("/{intersection_id}", response_model=IntersectionDetailResponse)
def get_intersection(
    intersection_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> IntersectionDetailResponse:
    intersection = traffic_operations.get_intersection(db, intersection_id)
    if intersection is None:
        raise HTTPException(status_code=404, detail="Intersection not found.")
    return intersection


@router.get("/{intersection_id}/live", response_model=IntersectionLiveResponse)
def get_intersection_live_state(
    intersection_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> IntersectionLiveResponse:
    live_state = traffic_operations.get_intersection_live_state(db, intersection_id)
    if live_state is None:
        raise HTTPException(status_code=404, detail="Intersection not found.")
    return live_state
