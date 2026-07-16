import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.models.enums import IncidentStatus
from app.repositories import traffic_operations
from app.schemas.common import PaginatedResponse
from app.schemas.traffic_operations import IncidentResponse


router = APIRouter(prefix="/incidents", tags=["traffic operations"])


@router.get("", response_model=PaginatedResponse[IncidentResponse])
def list_incidents(
    intersection_id: uuid.UUID | None = None,
    status: IncidentStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse[IncidentResponse]:
    items, total = traffic_operations.list_incidents(
        db,
        intersection_id=intersection_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(items=list(items), total=total, limit=limit, offset=offset)
