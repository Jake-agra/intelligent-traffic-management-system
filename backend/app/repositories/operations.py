import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.history import AuditLog, SignalEvent
from app.models.traffic import Alert, ControllerState, Incident, Intersection, Lane, SignalState


def get_alert(db: Session, alert_id: uuid.UUID) -> Alert | None:
    return db.get(Alert, alert_id)


def get_incident(db: Session, incident_id: uuid.UUID) -> Incident | None:
    return db.get(Incident, incident_id)


def get_intersection(db: Session, intersection_id: uuid.UUID) -> Intersection | None:
    return db.get(Intersection, intersection_id)


def get_lane_for_intersection(
    db: Session,
    *,
    lane_id: uuid.UUID,
    intersection_id: uuid.UUID,
) -> Lane | None:
    return db.scalar(
        select(Lane).where(
            Lane.id == lane_id,
            Lane.intersection_id == intersection_id,
        )
    )


def get_latest_signal_state(
    db: Session,
    *,
    intersection_id: uuid.UUID,
    lane_id: uuid.UUID | None,
) -> SignalState | None:
    statement = (
        select(SignalState)
        .where(SignalState.intersection_id == intersection_id)
        .order_by(SignalState.started_at.desc())
    )
    if lane_id is None:
        statement = statement.where(SignalState.lane_id.is_(None))
    else:
        statement = statement.where(SignalState.lane_id == lane_id)
    return db.scalar(statement)


def list_lanes_for_intersection(
    db: Session,
    *,
    intersection_id: uuid.UUID,
) -> list[Lane]:
    return list(
        db.scalars(
            select(Lane)
            .where(Lane.intersection_id == intersection_id)
            .order_by(Lane.sequence, Lane.name)
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


def add_controller_state(
    db: Session,
    controller_state: ControllerState,
) -> ControllerState:
    db.add(controller_state)
    db.flush()
    return controller_state


def add_audit_log(db: Session, audit_log: AuditLog) -> AuditLog:
    db.add(audit_log)
    db.flush()
    return audit_log


def add_signal_event(db: Session, signal_event: SignalEvent) -> SignalEvent:
    db.add(signal_event)
    db.flush()
    return signal_event


def add_signal_state(db: Session, signal_state: SignalState) -> SignalState:
    db.add(signal_state)
    db.flush()
    return signal_state
