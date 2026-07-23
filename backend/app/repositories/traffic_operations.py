from datetime import UTC, datetime
from typing import TypeVar
import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import AlertStatus, DeviceStatus, IncidentStatus
from app.models.mixins import utc_now
from app.models.traffic import (
    Alert,
    ControllerState,
    Device,
    Incident,
    Intersection,
    SignalState,
    TrafficReading,
    Violation,
)
from app.schemas.traffic_operations import (
    DashboardSummaryResponse,
    IntersectionLiveResponse,
)


ModelT = TypeVar("ModelT")


def list_intersections(db: Session) -> list[Intersection]:
    return list(
        db.scalars(
            select(Intersection)
            .where(Intersection.is_active.is_(True))
            .order_by(Intersection.name)
        )
    )


def get_intersection(db: Session, intersection_id: uuid.UUID) -> Intersection | None:
    return db.scalar(
        select(Intersection)
        .options(selectinload(Intersection.lanes))
        .where(Intersection.id == intersection_id)
    )


def get_intersection_live_state(
    db: Session,
    intersection_id: uuid.UUID,
) -> IntersectionLiveResponse | None:
    intersection = get_intersection(db, intersection_id)
    if intersection is None:
        return None

    return IntersectionLiveResponse(
        intersection=intersection,
        lanes=sorted(intersection.lanes, key=lambda lane: (lane.sequence, lane.name)),
        latest_traffic_readings=list_latest_traffic_readings(
            db,
            intersection_id=intersection_id,
            limit=20,
        ),
        current_signal_states=list_current_signal_states(
            db,
            intersection_id=intersection_id,
            limit=20,
        ),
        active_incidents=list_active_incidents(
            db,
            intersection_id=intersection_id,
            limit=20,
        ),
        recent_violations=list_recent_violations(
            db,
            intersection_id=intersection_id,
            limit=20,
        ),
        active_alerts=list_active_alerts(
            db,
            intersection_id=intersection_id,
            limit=20,
        ),
        devices=list_device_health(
            db,
            intersection_id=intersection_id,
            limit=100,
        ),
        controller_state=get_controller_state(db, intersection_id=intersection_id),
        generated_at=utc_now(),
    )


def list_latest_traffic_readings(
    db: Session,
    *,
    intersection_id: uuid.UUID,
    limit: int,
) -> list[TrafficReading]:
    readings = list(
        db.scalars(
            select(TrafficReading)
            .where(TrafficReading.intersection_id == intersection_id)
            .order_by(TrafficReading.captured_at.desc(), TrafficReading.id.desc())
        )
    )
    return _latest_per_lane(readings, "captured_at", limit=limit)


def list_current_signal_states(
    db: Session,
    *,
    intersection_id: uuid.UUID,
    limit: int,
) -> list[SignalState]:
    states = list(
        db.scalars(
            select(SignalState)
            .where(SignalState.intersection_id == intersection_id)
            .order_by(SignalState.started_at.desc(), SignalState.id.desc())
        )
    )
    return _latest_per_lane(states, "started_at", limit=limit)


def list_active_incidents(
    db: Session,
    *,
    intersection_id: uuid.UUID,
    limit: int,
) -> list[Incident]:
    return list(
        db.scalars(
            select(Incident)
            .where(
                Incident.intersection_id == intersection_id,
                Incident.status != IncidentStatus.RESOLVED,
            )
            .order_by(Incident.reported_at.desc())
            .limit(limit)
        )
    )


def list_recent_violations(
    db: Session,
    *,
    intersection_id: uuid.UUID,
    limit: int,
) -> list[Violation]:
    return list(
        db.scalars(
            select(Violation)
            .where(Violation.intersection_id == intersection_id)
            .order_by(Violation.occurred_at.desc())
            .limit(limit)
        )
    )


def list_active_alerts(
    db: Session,
    *,
    intersection_id: uuid.UUID,
    limit: int,
) -> list[Alert]:
    return list(
        db.scalars(
            select(Alert)
            .where(
                Alert.intersection_id == intersection_id,
                Alert.status != AlertStatus.RESOLVED,
            )
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )
    )


def list_device_health(
    db: Session,
    *,
    intersection_id: uuid.UUID,
    limit: int,
) -> list[Device]:
    return list(
        db.scalars(
            select(Device)
            .where(Device.intersection_id == intersection_id)
            .order_by(Device.name)
            .limit(limit)
        )
    )


def get_controller_state(
    db: Session,
    *,
    intersection_id: uuid.UUID,
) -> ControllerState | None:
    return db.scalar(
        select(ControllerState).where(ControllerState.intersection_id == intersection_id)
    )


def list_incidents(
    db: Session,
    *,
    intersection_id: uuid.UUID | None,
    status: IncidentStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Incident], int]:
    statement = select(Incident).order_by(Incident.reported_at.desc())
    statement = _filter_by_intersection(statement, Incident.intersection_id, intersection_id)
    if status is not None:
        statement = statement.where(Incident.status == status)
    return _paginate(db, statement, limit=limit, offset=offset)


def list_violations(
    db: Session,
    *,
    intersection_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Violation], int]:
    statement = select(Violation).order_by(Violation.occurred_at.desc())
    statement = _filter_by_intersection(
        statement,
        Violation.intersection_id,
        intersection_id,
    )
    return _paginate(db, statement, limit=limit, offset=offset)


def list_alerts(
    db: Session,
    *,
    intersection_id: uuid.UUID | None,
    status: AlertStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Alert], int]:
    statement = select(Alert).order_by(Alert.created_at.desc())
    statement = _filter_by_intersection(statement, Alert.intersection_id, intersection_id)
    if status is not None:
        statement = statement.where(Alert.status == status)
    return _paginate(db, statement, limit=limit, offset=offset)


def list_devices(
    db: Session,
    *,
    intersection_id: uuid.UUID | None,
    status: DeviceStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Device], int]:
    statement = select(Device).order_by(Device.name)
    statement = _filter_by_intersection(statement, Device.intersection_id, intersection_id)
    if status is not None:
        statement = statement.where(Device.status == status)
    return _paginate(db, statement, limit=limit, offset=offset)


def get_dashboard_summary(db: Session) -> DashboardSummaryResponse:
    generated_at = utc_now()
    latest_reading_at = _ensure_timezone(
        db.scalar(select(func.max(TrafficReading.captured_at)))
    )

    return DashboardSummaryResponse(
        generated_at=generated_at,
        intersections={
            "total": _count(db, select(Intersection)),
            "active": _count(db, select(Intersection).where(Intersection.is_active.is_(True))),
        },
        traffic={
            "latest_reading_at": latest_reading_at,
            "total_readings": _count(db, select(TrafficReading)),
        },
        signals={
            "current_states": _count(db, select(SignalState)),
        },
        incidents={
            "active": _count(
                db,
                select(Incident).where(Incident.status != IncidentStatus.RESOLVED),
            ),
            "total": _count(db, select(Incident)),
        },
        violations={
            "recent": _count(db, select(Violation)),
            "total": _count(db, select(Violation)),
        },
        alerts={
            "active": _count(db, select(Alert).where(Alert.status != AlertStatus.RESOLVED)),
            "total": _count(db, select(Alert)),
        },
        devices={
            "total": _count(db, select(Device)),
            "online": _count(db, select(Device).where(Device.status == DeviceStatus.ONLINE)),
            "offline": _count(
                db,
                select(Device).where(Device.status == DeviceStatus.OFFLINE),
            ),
            "degraded": _count(
                db,
                select(Device).where(Device.status == DeviceStatus.DEGRADED),
            ),
        },
    )


def _ensure_timezone(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _latest_per_lane(
    items: list[ModelT],
    timestamp_attribute: str,
    *,
    limit: int,
) -> list[ModelT]:
    latest: dict[uuid.UUID | str, ModelT] = {}
    for item in items:
        lane_id = getattr(item, "lane_id", None)
        key = lane_id if lane_id is not None else "intersection"
        current = latest.get(key)
        if current is None or _is_later_authoritative(item, current, timestamp_attribute):
            latest[key] = item
    return sorted(
        latest.values(),
        key=lambda item: (
            getattr(item, timestamp_attribute),
            str(getattr(item, "id")),
        ),
        reverse=True,
    )[:limit]


def _is_later_authoritative(
    candidate: ModelT,
    current: ModelT,
    timestamp_attribute: str,
) -> bool:
    candidate_timestamp = getattr(candidate, timestamp_attribute)
    current_timestamp = getattr(current, timestamp_attribute)
    if candidate_timestamp != current_timestamp:
        return candidate_timestamp > current_timestamp
    return str(getattr(candidate, "id")) > str(getattr(current, "id"))


def _paginate(
    db: Session,
    statement: Select[tuple[ModelT]],
    *,
    limit: int,
    offset: int,
) -> tuple[list[ModelT], int]:
    total = _count(db, statement)
    items = list(db.scalars(statement.limit(limit).offset(offset)))
    return items, total


def _count(db: Session, statement: Select[tuple[object]]) -> int:
    return int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)


def _filter_by_intersection(
    statement: Select[tuple[ModelT]],
    column: object,
    intersection_id: uuid.UUID | None,
) -> Select[tuple[ModelT]]:
    if intersection_id is None:
        return statement
    return statement.where(column == intersection_id)
