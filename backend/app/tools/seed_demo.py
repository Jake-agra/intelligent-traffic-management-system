from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
import getpass
import os
from typing import Sequence
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.models import Base
from app.models.enums import (
    DeviceStatus,
    DeviceType,
    OperatingMode,
    SignalColor,
    TrafficDensity,
    UserRole,
)
from app.models.traffic import Device, Intersection, Lane, SignalState, TrafficReading
from app.models.user import User
from app.security.passwords import hash_password, verify_password


DEMO_INTERSECTION_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEMO_LANE_IDS = {
    "north": uuid.UUID("00000000-0000-0000-0000-000000000101"),
    "south": uuid.UUID("00000000-0000-0000-0000-000000000102"),
    "east": uuid.UUID("00000000-0000-0000-0000-000000000103"),
    "west": uuid.UUID("00000000-0000-0000-0000-000000000104"),
}
DEMO_DEVICE_ID = uuid.UUID("00000000-0000-0000-0000-000000000201")
DEMO_TRAFFIC_READING_IDS = {
    "north": uuid.UUID("00000000-0000-0000-0000-000000000301"),
    "south": uuid.UUID("00000000-0000-0000-0000-000000000302"),
    "east": uuid.UUID("00000000-0000-0000-0000-000000000303"),
    "west": uuid.UUID("00000000-0000-0000-0000-000000000304"),
}
DEMO_TRAFFIC_READINGS = {
    "north": {"vehicle_count": 4, "density": TrafficDensity.LOW},
    "south": {"vehicle_count": 3, "density": TrafficDensity.LOW},
    "east": {"vehicle_count": 7, "density": TrafficDensity.MEDIUM},
    "west": {"vehicle_count": 5, "density": TrafficDensity.MEDIUM},
}


@dataclass(frozen=True)
class DemoSeedConfig:
    admin_email: str
    admin_password: str
    admin_display_name: str = "Demo Admin"
    allow_production: bool = False
    with_traffic: bool = False


@dataclass(frozen=True)
class DemoSeedResult:
    statuses: Counter[str]
    intersection_id: uuid.UUID
    lane_ids: dict[str, uuid.UUID]


def seed_demo(session: Session, config: DemoSeedConfig) -> DemoSeedResult:
    statuses: Counter[str] = Counter()

    statuses[_ensure_admin_user(session, config)] += 1
    statuses[
        _ensure_by_id(
            session,
            Intersection,
            DEMO_INTERSECTION_ID,
            {
                "name": "Demo Four-Way Intersection",
                "location_description": "Local development demo intersection",
                "latitude": None,
                "longitude": None,
                "is_active": True,
            },
        )
    ] += 1

    for sequence, direction in enumerate(("north", "south", "east", "west"), start=1):
        statuses[
            _ensure_by_id(
                session,
                Lane,
                DEMO_LANE_IDS[direction],
                {
                    "intersection_id": DEMO_INTERSECTION_ID,
                    "name": f"{direction.title()}bound",
                    "direction": direction,
                    "sequence": sequence,
                    "is_active": True,
                },
            )
        ] += 1

    statuses[
        _ensure_by_id(
            session,
            Device,
            DEMO_DEVICE_ID,
            {
                "intersection_id": DEMO_INTERSECTION_ID,
                "lane_id": None,
                "identifier": "demo-rpi-edge-001",
                "name": "Demo Raspberry Pi Edge Controller",
                "type": DeviceType.RASPBERRY_PI,
                "status": DeviceStatus.OFFLINE,
                "last_seen_at": None,
            },
        )
    ] += 1

    for direction, lane_id in DEMO_LANE_IDS.items():
        statuses[_ensure_safe_red_signal_state(session, lane_id)] += 1

    if config.with_traffic:
        for direction, lane_id in DEMO_LANE_IDS.items():
            status = _ensure_demo_traffic_reading(session, direction, lane_id)
            statuses[f"traffic_{status}"] += 1

    session.commit()
    return DemoSeedResult(
        statuses=statuses,
        intersection_id=DEMO_INTERSECTION_ID,
        lane_ids=dict(DEMO_LANE_IDS),
    )


def assert_safe_environment(environment: str, *, allow_production: bool) -> None:
    if environment.lower() in {"prod", "production"} and not allow_production:
        raise SystemExit(
            "Refusing to seed demo data in production. "
            "Pass --allow-production only for a deliberate recovery/demo operation."
        )


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    settings = get_settings()
    password = args.password or os.getenv("DEMO_ADMIN_PASSWORD")
    if password is None:
        password = getpass.getpass("Demo admin password: ")
    if not password:
        raise SystemExit("A demo admin password is required.")

    email = args.email or os.getenv("DEMO_ADMIN_EMAIL") or "admin@example.com"
    config = DemoSeedConfig(
        admin_email=email.lower(),
        admin_password=password,
        admin_display_name=args.display_name,
        allow_production=args.allow_production,
        with_traffic=args.with_traffic,
    )
    assert_safe_environment(settings.environment, allow_production=config.allow_production)

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        result = seed_demo(session, config)

    _print_result(result, config.admin_email)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed local demo backend data.")
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--display-name", default="Demo Admin")
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument(
        "--with-traffic",
        action="store_true",
        help="Add or refresh one recent demo traffic reading for each approach.",
    )
    return parser.parse_args(argv)


def _ensure_admin_user(session: Session, config: DemoSeedConfig) -> str:
    user = session.scalar(select(User).where(User.email == config.admin_email.lower()))
    if user is None:
        session.add(
            User(
                email=config.admin_email.lower(),
                display_name=config.admin_display_name,
                password_hash=hash_password(config.admin_password),
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        return "created"

    changed = False
    if user.display_name != config.admin_display_name:
        user.display_name = config.admin_display_name
        changed = True
    if user.role != UserRole.ADMIN:
        user.role = UserRole.ADMIN
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    if not verify_password(config.admin_password, user.password_hash):
        user.password_hash = hash_password(config.admin_password)
        changed = True
    return "updated" if changed else "existing"


def _ensure_by_id(
    session: Session,
    model,
    object_id: uuid.UUID,
    values: dict[str, object],
) -> str:
    instance = session.get(model, object_id)
    if instance is None:
        session.add(model(id=object_id, **values))
        return "created"

    changed = False
    for field, value in values.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed = True
    return "updated" if changed else "existing"


def _ensure_safe_red_signal_state(session: Session, lane_id: uuid.UUID) -> str:
    state = session.scalar(
        select(SignalState).where(
            SignalState.intersection_id == DEMO_INTERSECTION_ID,
            SignalState.lane_id == lane_id,
        )
    )
    if state is None:
        session.add(
            SignalState(
                intersection_id=DEMO_INTERSECTION_ID,
                lane_id=lane_id,
                color=SignalColor.RED,
                operating_mode=OperatingMode.MANUAL,
                started_at=datetime.now(UTC),
                ends_at=None,
            )
        )
        return "created"

    changed = False
    if state.color != SignalColor.RED:
        state.color = SignalColor.RED
        state.started_at = datetime.now(UTC)
        changed = True
    if state.operating_mode != OperatingMode.MANUAL:
        state.operating_mode = OperatingMode.MANUAL
        changed = True
    if state.ends_at is not None:
        state.ends_at = None
        changed = True
    return "updated" if changed else "existing"


def _ensure_demo_traffic_reading(
    session: Session,
    direction: str,
    lane_id: uuid.UUID,
) -> str:
    values = DEMO_TRAFFIC_READINGS[direction]
    reading = session.get(TrafficReading, DEMO_TRAFFIC_READING_IDS[direction])
    captured_at = datetime.now(UTC)
    if reading is None:
        session.add(
            TrafficReading(
                id=DEMO_TRAFFIC_READING_IDS[direction],
                intersection_id=DEMO_INTERSECTION_ID,
                lane_id=lane_id,
                device_id=DEMO_DEVICE_ID,
                vehicle_count=int(values["vehicle_count"]),
                density=values["density"],
                captured_at=captured_at,
            )
        )
        return "created"

    changed = False
    updates = {
        "intersection_id": DEMO_INTERSECTION_ID,
        "lane_id": lane_id,
        "device_id": DEMO_DEVICE_ID,
        "vehicle_count": int(values["vehicle_count"]),
        "density": values["density"],
    }
    for field, value in updates.items():
        if getattr(reading, field) != value:
            setattr(reading, field, value)
            changed = True
    if reading.captured_at != captured_at:
        reading.captured_at = captured_at
        changed = True
    return "updated" if changed else "existing"


def _print_result(result: DemoSeedResult, admin_email: str) -> None:
    print("Demo seed complete")
    print(f"Admin email: {admin_email}")
    print(f"Intersection ID: {result.intersection_id}")
    for direction, lane_id in result.lane_ids.items():
        print(f"{direction.title()} lane ID: {lane_id}")
    print(
        "Records: "
        f"created={result.statuses['created']} "
        f"updated={result.statuses['updated']} "
        f"existing={result.statuses['existing']}"
    )
    traffic_rows = (
        result.statuses["traffic_created"]
        + result.statuses["traffic_updated"]
        + result.statuses["traffic_existing"]
    )
    if traffic_rows:
        print(f"Demo traffic readings: {traffic_rows}")


if __name__ == "__main__":
    main()
