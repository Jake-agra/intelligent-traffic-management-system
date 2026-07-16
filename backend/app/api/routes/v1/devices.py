import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_roles
from app.models.enums import DeviceStatus
from app.models.enums import UserRole
from app.repositories import traffic_operations
from app.schemas.common import PaginatedResponse
from app.schemas.traffic_operations import DeviceHealthResponse


router = APIRouter(prefix="/devices", tags=["traffic operations"])


@router.get("", response_model=PaginatedResponse[DeviceHealthResponse])
def list_devices(
    intersection_id: uuid.UUID | None = None,
    status: DeviceStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user=Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse[DeviceHealthResponse]:
    items, total = traffic_operations.list_devices(
        db,
        intersection_id=intersection_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(items=list(items), total=total, limit=limit, offset=offset)
