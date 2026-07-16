import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_roles
from app.models.enums import IncidentStatus
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import traffic_operations
from app.schemas.common import PaginatedResponse
from app.schemas.operations import IncidentActionResponse, OperationalActionRequest
from app.schemas.traffic_operations import IncidentResponse
from app.services import operations


router = APIRouter(prefix="/incidents", tags=["traffic operations"])


@router.get("", response_model=PaginatedResponse[IncidentResponse])
def list_incidents(
    intersection_id: uuid.UUID | None = None,
    status: IncidentStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user=Depends(
        require_roles(UserRole.ADMIN, UserRole.EMERGENCY_RESPONDER)
    ),
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


@router.post("/{incident_id}/acknowledge", response_model=IncidentActionResponse)
async def acknowledge_incident(
    incident_id: uuid.UUID,
    request: OperationalActionRequest,
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.EMERGENCY_RESPONDER)
    ),
    db: Session = Depends(get_db_session),
) -> IncidentActionResponse:
    return await operations.acknowledge_incident(
        db,
        incident_id=incident_id,
        reason=request.reason,
        user=current_user,
    )


@router.post("/{incident_id}/respond", response_model=IncidentActionResponse)
async def respond_to_incident(
    incident_id: uuid.UUID,
    request: OperationalActionRequest,
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.EMERGENCY_RESPONDER)
    ),
    db: Session = Depends(get_db_session),
) -> IncidentActionResponse:
    return await operations.respond_to_incident(
        db,
        incident_id=incident_id,
        reason=request.reason,
        user=current_user,
    )


@router.post("/{incident_id}/resolve", response_model=IncidentActionResponse)
async def resolve_incident(
    incident_id: uuid.UUID,
    request: OperationalActionRequest,
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.EMERGENCY_RESPONDER)
    ),
    db: Session = Depends(get_db_session),
) -> IncidentActionResponse:
    return await operations.resolve_incident(
        db,
        incident_id=incident_id,
        reason=request.reason,
        user=current_user,
    )
