from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_roles
from app.models.enums import UserRole
from app.repositories import traffic_operations
from app.schemas.traffic_operations import DashboardSummaryResponse


router = APIRouter(prefix="/dashboard", tags=["traffic operations"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    _current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db_session),
) -> DashboardSummaryResponse:
    return traffic_operations.get_dashboard_summary(db)
