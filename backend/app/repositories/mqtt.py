import uuid

from sqlalchemy.orm import Session

from app.models.history import DeviceEvent
from app.models.traffic import Device, Intersection, Lane, TrafficReading


def get_device(db: Session, device_id: uuid.UUID) -> Device | None:
    return db.get(Device, device_id)


def get_intersection(db: Session, intersection_id: uuid.UUID) -> Intersection | None:
    return db.get(Intersection, intersection_id)


def get_lane(db: Session, lane_id: uuid.UUID) -> Lane | None:
    return db.get(Lane, lane_id)


def add_device_event(db: Session, device_event: DeviceEvent) -> DeviceEvent:
    db.add(device_event)
    db.flush()
    return device_event


def add_traffic_reading(db: Session, traffic_reading: TrafficReading) -> TrafficReading:
    db.add(traffic_reading)
    db.flush()
    return traffic_reading
