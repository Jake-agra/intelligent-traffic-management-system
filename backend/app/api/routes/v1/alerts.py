import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db_session
from app.models.enums import AlertStatus
from app.models.user import User
from app.repositories import traffic_operations
from app.schemas.common import PaginatedResponse
from app.schemas.operations import AlertActionResponse, OperationalActionRequest
from app.schemas.traffic_operations import AlertResponse
from app.services import operations


router = APIRouter(prefix="/alerts", tags=["traffic operations"])


@router.get("", response_model=PaginatedResponse[AlertResponse])
async def list_alerts(
    intersection_id: uuid.UUID | None = None,
    status: AlertStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user=Depends(get_active_user),
    db: Session = Depends(get_db_session),
) -> PaginatedResponse[AlertResponse]:
    items, total = traffic_operations.list_alerts(
        db,
        intersection_id=intersection_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(items=list(items), total=total, limit=limit, offset=offset)


@router.post("/{alert_id}/acknowledge", response_model=AlertActionResponse)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    request: OperationalActionRequest,
    current_user: User = Depends(get_active_user),
    db: Session = Depends(get_db_session),
) -> AlertActionResponse:
    return await operations.acknowledge_alert(
        db,
        alert_id=alert_id,
        reason=request.reason,
        user=current_user,
    )


@router.post("/{alert_id}/resolve", response_model=AlertActionResponse)
async def resolve_alert(
    alert_id: uuid.UUID,
    request: OperationalActionRequest,
    current_user: User = Depends(get_active_user),
    db: Session = Depends(get_db_session),
) -> AlertActionResponse:
    return await operations.resolve_alert(
        db,
        alert_id=alert_id,
        reason=request.reason,
        user=current_user,
    )
