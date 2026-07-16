from datetime import UTC, datetime, timedelta
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import (
    AlertStatus,
    IncidentStatus,
    OperatingMode,
    SignalColor,
    SignalEventSource,
    UserRole,
)
from app.models.history import AuditLog, SignalEvent
from app.models.traffic import Alert, Incident, SignalState
from app.models.user import User
from app.realtime import realtime_event_publisher
from app.repositories import operations
from app.schemas.operations import (
    AlertActionResponse,
    IncidentActionResponse,
    SignalModeResponse,
    SignalOverrideResponse,
)
from app.schemas.realtime import RealtimeEventEnvelope, RealtimeEventName


async def acknowledge_alert(
    db: Session,
    *,
    alert_id: uuid.UUID,
    reason: str,
    user: User,
) -> AlertActionResponse:
    _require_role(user, UserRole.ADMIN, UserRole.POLICE, UserRole.EMERGENCY_RESPONDER)
    alert = _get_alert_or_404(db, alert_id)
    if alert.status == AlertStatus.RESOLVED:
        raise _conflict("Resolved alerts cannot be acknowledged.")

    before = _alert_state(alert)
    now = datetime.now(UTC)
    if alert.status != AlertStatus.ACKNOWLEDGED:
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = now
        alert.acknowledged_by_id = user.id
    after = _alert_state(alert)

    audit = _audit(
        db,
        user=user,
        action="alert.acknowledge",
        resource_type="alert",
        resource_id=alert.id,
        before_state=before,
        after_state=after | {"reason": reason},
    )
    db.commit()
    await _publish(
        RealtimeEventName.ALERT_ACKNOWLEDGED,
        intersection_id=alert.intersection_id,
        data={"alert_id": str(alert.id), "status": alert.status.value},
    )
    return AlertActionResponse(
        action="alert.acknowledge",
        audit_log_id=audit.id,
        emitted_event=RealtimeEventName.ALERT_ACKNOWLEDGED.value,
        alert=alert,
        status=alert.status,
    )


async def resolve_alert(
    db: Session,
    *,
    alert_id: uuid.UUID,
    reason: str,
    user: User,
) -> AlertActionResponse:
    _require_role(user, UserRole.ADMIN)
    alert = _get_alert_or_404(db, alert_id)
    before = _alert_state(alert)
    now = datetime.now(UTC)
    if alert.status != AlertStatus.RESOLVED:
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = now
    after = _alert_state(alert)
    audit = _audit(
        db,
        user=user,
        action="alert.resolve",
        resource_type="alert",
        resource_id=alert.id,
        before_state=before,
        after_state=after | {"reason": reason},
    )
    db.commit()
    await _publish(
        RealtimeEventName.ALERT_ACKNOWLEDGED,
        intersection_id=alert.intersection_id,
        data={"alert_id": str(alert.id), "status": alert.status.value},
    )
    return AlertActionResponse(
        action="alert.resolve",
        audit_log_id=audit.id,
        emitted_event=RealtimeEventName.ALERT_ACKNOWLEDGED.value,
        alert=alert,
        status=alert.status,
    )


async def acknowledge_incident(
    db: Session,
    *,
    incident_id: uuid.UUID,
    reason: str,
    user: User,
) -> IncidentActionResponse:
    _require_role(user, UserRole.ADMIN, UserRole.EMERGENCY_RESPONDER)
    incident = _get_incident_or_404(db, incident_id)
    if incident.status == IncidentStatus.RESOLVED:
        raise _conflict("Resolved incidents cannot be acknowledged.")
    return await _set_incident_status(
        db,
        incident=incident,
        user=user,
        reason=reason,
        action="incident.acknowledge",
        status_value=IncidentStatus.INVESTIGATING,
    )


async def respond_to_incident(
    db: Session,
    *,
    incident_id: uuid.UUID,
    reason: str,
    user: User,
) -> IncidentActionResponse:
    _require_role(user, UserRole.ADMIN, UserRole.EMERGENCY_RESPONDER)
    incident = _get_incident_or_404(db, incident_id)
    if incident.status == IncidentStatus.RESOLVED:
        raise _conflict("Resolved incidents cannot receive response updates.")
    return await _set_incident_status(
        db,
        incident=incident,
        user=user,
        reason=reason,
        action="incident.respond",
        status_value=IncidentStatus.INVESTIGATING,
    )


async def resolve_incident(
    db: Session,
    *,
    incident_id: uuid.UUID,
    reason: str,
    user: User,
) -> IncidentActionResponse:
    _require_role(user, UserRole.ADMIN, UserRole.EMERGENCY_RESPONDER)
    incident = _get_incident_or_404(db, incident_id)
    return await _set_incident_status(
        db,
        incident=incident,
        user=user,
        reason=reason,
        action="incident.resolve",
        status_value=IncidentStatus.RESOLVED,
    )


async def change_signal_mode(
    db: Session,
    *,
    intersection_id: uuid.UUID,
    mode: OperatingMode,
    reason: str,
    user: User,
) -> SignalModeResponse:
    _require_role(user, UserRole.ADMIN)
    intersection = operations.get_intersection(db, intersection_id)
    if intersection is None:
        raise HTTPException(status_code=404, detail="Intersection not found.")

    before_state = {"intersection_id": str(intersection_id)}
    now = datetime.now(UTC)
    signal_event = operations.add_signal_event(
        db,
        SignalEvent(
            intersection_id=intersection_id,
            previous_color=SignalColor.YELLOW,
            new_color=SignalColor.YELLOW,
            operating_mode=mode,
            duration_seconds=0,
            reason=reason,
            user_id=user.id,
            source=SignalEventSource.MANUAL,
            occurred_at=now,
        ),
    )
    for lane in operations.list_lanes_for_intersection(db, intersection_id=intersection_id):
        latest = operations.get_latest_signal_state(
            db,
            intersection_id=intersection_id,
            lane_id=lane.id,
        )
        operations.add_signal_state(
            db,
            SignalState(
                intersection_id=intersection_id,
                lane_id=lane.id,
                color=latest.color if latest else SignalColor.RED,
                operating_mode=mode,
                started_at=now,
            ),
        )
    audit = _audit(
        db,
        user=user,
        action="signal.mode_change",
        resource_type="intersection",
        resource_id=intersection_id,
        before_state=before_state,
        after_state={"mode": mode.value, "reason": reason},
    )
    db.commit()
    await _publish(
        RealtimeEventName.SIGNAL_UPDATED,
        intersection_id=intersection_id,
        data={"mode": mode.value, "reason": reason},
    )
    return SignalModeResponse(
        action="signal.mode_change",
        audit_log_id=audit.id,
        emitted_event=RealtimeEventName.SIGNAL_UPDATED.value,
        intersection_id=intersection_id,
        mode=mode,
        reason=reason,
    )


async def override_signal(
    db: Session,
    *,
    intersection_id: uuid.UUID,
    lane_id: uuid.UUID,
    requested_color: SignalColor,
    duration_seconds: int,
    reason: str,
    user: User,
) -> SignalOverrideResponse:
    _require_role(user, UserRole.ADMIN)
    settings = get_settings()
    if duration_seconds > settings.max_signal_override_seconds:
        raise _conflict("Signal override duration exceeds configured maximum.")
    intersection = operations.get_intersection(db, intersection_id)
    if intersection is None:
        raise HTTPException(status_code=404, detail="Intersection not found.")
    lane = operations.get_lane_for_intersection(
        db,
        lane_id=lane_id,
        intersection_id=intersection_id,
    )
    if lane is None:
        raise HTTPException(status_code=404, detail="Lane not found for intersection.")

    latest = operations.get_latest_signal_state(
        db,
        intersection_id=intersection_id,
        lane_id=lane_id,
    )
    previous_color = latest.color if latest else SignalColor.RED
    if previous_color == SignalColor.GREEN and requested_color == SignalColor.RED:
        raise _conflict("Unsafe signal transition from green to red.")

    now = datetime.now(UTC)
    ends_at = now + timedelta(seconds=duration_seconds)
    signal_state = operations.add_signal_state(
        db,
        SignalState(
            intersection_id=intersection_id,
            lane_id=lane_id,
            color=requested_color,
            operating_mode=OperatingMode.MANUAL,
            started_at=now,
            ends_at=ends_at,
        ),
    )
    signal_event = operations.add_signal_event(
        db,
        SignalEvent(
            intersection_id=intersection_id,
            lane_id=lane_id,
            previous_color=previous_color,
            new_color=requested_color,
            operating_mode=OperatingMode.MANUAL,
            duration_seconds=duration_seconds,
            reason=reason,
            user_id=user.id,
            source=SignalEventSource.MANUAL,
            occurred_at=now,
        ),
    )
    audit = _audit(
        db,
        user=user,
        action="signal.override",
        resource_type="lane",
        resource_id=lane_id,
        before_state={"color": previous_color.value},
        after_state={
            "color": requested_color.value,
            "duration_seconds": duration_seconds,
            "reason": reason,
        },
    )
    db.commit()
    await _publish(
        RealtimeEventName.SIGNAL_UPDATED,
        intersection_id=intersection_id,
        data={
            "signal_state_id": str(signal_state.id),
            "lane_id": str(lane_id),
            "color": requested_color.value,
            "duration_seconds": duration_seconds,
        },
    )
    return SignalOverrideResponse(
        action="signal.override",
        audit_log_id=audit.id,
        emitted_event=RealtimeEventName.SIGNAL_UPDATED.value,
        intersection_id=intersection_id,
        lane_id=lane_id,
        color=requested_color,
        duration_seconds=duration_seconds,
        started_at=now,
        ends_at=ends_at,
        signal_event_id=signal_event.id,
    )


async def _set_incident_status(
    db: Session,
    *,
    incident: Incident,
    user: User,
    reason: str,
    action: str,
    status_value: IncidentStatus,
) -> IncidentActionResponse:
    before = _incident_state(incident)
    if status_value == IncidentStatus.RESOLVED and incident.status != IncidentStatus.RESOLVED:
        incident.resolved_at = datetime.now(UTC)
    incident.status = status_value
    after = _incident_state(incident)
    audit = _audit(
        db,
        user=user,
        action=action,
        resource_type="incident",
        resource_id=incident.id,
        before_state=before,
        after_state=after | {"reason": reason},
    )
    db.commit()
    await _publish(
        RealtimeEventName.INCIDENT_UPDATED,
        intersection_id=incident.intersection_id,
        data={"incident_id": str(incident.id), "status": incident.status.value},
    )
    return IncidentActionResponse(
        action=action,
        audit_log_id=audit.id,
        emitted_event=RealtimeEventName.INCIDENT_UPDATED.value,
        incident=incident,
        status=incident.status,
    )


def _get_alert_or_404(db: Session, alert_id: uuid.UUID) -> Alert:
    alert = operations.get_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return alert


def _get_incident_or_404(db: Session, incident_id: uuid.UUID) -> Incident:
    incident = operations.get_incident(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return incident


def _require_role(user: User, *roles: UserRole) -> None:
    if user.role not in set(roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role.")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _alert_state(alert: Alert) -> dict[str, object]:
    return {
        "status": alert.status.value,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }


def _incident_state(incident: Incident) -> dict[str, object]:
    return {
        "status": incident.status.value,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
    }


def _audit(
    db: Session,
    *,
    user: User,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    before_state: dict[str, object] | None,
    after_state: dict[str, object] | None,
) -> AuditLog:
    return operations.add_audit_log(
        db,
        AuditLog(
            user_id=user.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            occurred_at=datetime.now(UTC),
        ),
    )


async def _publish(
    event_name: RealtimeEventName,
    *,
    intersection_id: uuid.UUID | None,
    data: dict[str, object],
) -> None:
    await realtime_event_publisher.publish(
        RealtimeEventEnvelope(
            event=event_name,
            intersection_id=intersection_id,
            data=data,
        )
    )
