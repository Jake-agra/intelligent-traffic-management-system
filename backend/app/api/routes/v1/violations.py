import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_roles
from app.models.enums import UserRole
from app.repositories import traffic_operations
from app.schemas.common import PaginatedResponse
from app.schemas.traffic_operations import ViolationResponse


router = APIRouter(prefix="/violations", tags=["traffic operations"])


@router.get("", response_model=PaginatedResponse[ViolationResponse])
def list_violations(
    intersection_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user=Depends(require_roles(UserRole.ADMIN, UserRole.POLICE)),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse[ViolationResponse]:
    items, total = traffic_operations.list_violations(
        db,
        intersection_id=intersection_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(items=list(items), total=total, limit=limit, offset=offset)
