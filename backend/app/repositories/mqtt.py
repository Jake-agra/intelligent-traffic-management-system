import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.history import DeviceEvent, SignalEvent
from app.models.traffic import (
    ControllerState,
    Device,
    Intersection,
    Lane,
    SignalState,
    TrafficReading,
)


def get_device(db: Session, device_id: uuid.UUID) -> Device | None:
    return db.get(Device, device_id)


def get_intersection(db: Session, intersection_id: uuid.UUID) -> Intersection | None:
    return db.get(Intersection, intersection_id)


def get_lane(db: Session, lane_id: uuid.UUID) -> Lane | None:
    return db.get(Lane, lane_id)


def get_lanes_for_intersection(db: Session, intersection_id: uuid.UUID) -> list[Lane]:
    return list(
        db.scalars(
            select(Lane)
            .where(Lane.intersection_id == intersection_id)
            .order_by(Lane.sequence, Lane.name)
        )
    )


def get_latest_signal_state(
    db: Session,
    *,
    intersection_id: uuid.UUID,
    lane_id: uuid.UUID,
) -> SignalState | None:
    return db.scalar(
        select(SignalState)
        .where(
            SignalState.intersection_id == intersection_id,
            SignalState.lane_id == lane_id,
        )
        .order_by(SignalState.started_at.desc(), SignalState.id.desc())
    )


def get_controller_state(
    db: Session,
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


def add_device_event(db: Session, device_event: DeviceEvent) -> DeviceEvent:
    db.add(device_event)
    db.flush()
    return device_event


def add_traffic_reading(db: Session, traffic_reading: TrafficReading) -> TrafficReading:
    db.add(traffic_reading)
    db.flush()
    return traffic_reading


def add_signal_state(db: Session, signal_state: SignalState) -> SignalState:
    db.add(signal_state)
    db.flush()
    return signal_state


def add_signal_event(db: Session, signal_event: SignalEvent) -> SignalEvent:
    db.add(signal_event)
    db.flush()
    return signal_event
