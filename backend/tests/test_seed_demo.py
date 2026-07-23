import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.enums import OperatingMode, SignalColor, TrafficDensity, UserRole
from app.models.traffic import Lane, SignalState, TrafficReading
from app.models.user import User
from app.security.passwords import verify_password
from app.tools.seed_demo import (
    DEMO_DEVICE_ID,
    DEMO_INTERSECTION_ID,
    DEMO_LANE_IDS,
    DemoSeedConfig,
    assert_safe_environment,
    seed_demo,
)


@pytest.fixture
def demo_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def test_seed_demo_creates_admin_intersection_lanes_and_safe_red_states(
    demo_session: Session,
) -> None:
    config = DemoSeedConfig(
        admin_email="admin@example.com",
        admin_password="local-secret",
    )

    result = seed_demo(demo_session, config)

    admin = demo_session.scalar(select(User).where(User.email == "admin@example.com"))
    lanes = demo_session.scalars(select(Lane)).all()
    signal_states = demo_session.scalars(select(SignalState)).all()

    assert result.statuses["created"] == 11
    assert result.intersection_id == DEMO_INTERSECTION_ID
    assert result.lane_ids == DEMO_LANE_IDS
    assert admin is not None
    assert admin.role == UserRole.ADMIN
    assert admin.password_hash != "local-secret"
    assert verify_password("local-secret", admin.password_hash)
    assert {lane.direction for lane in lanes} == {"north", "south", "east", "west"}
    assert {state.color for state in signal_states} == {SignalColor.RED}
    assert {state.operating_mode for state in signal_states} == {OperatingMode.MANUAL}


def test_seed_demo_is_idempotent(demo_session: Session) -> None:
    config = DemoSeedConfig(
        admin_email="admin@example.com",
        admin_password="local-secret",
    )

    first = seed_demo(demo_session, config)
    second = seed_demo(demo_session, config)

    assert first.statuses["created"] == 11
    assert second.statuses["existing"] == 11
    assert len(demo_session.scalars(select(Lane)).all()) == 4
    assert len(demo_session.scalars(select(SignalState)).all()) == 4


def test_seed_demo_optionally_adds_demo_traffic_readings(
    demo_session: Session,
) -> None:
    config = DemoSeedConfig(
        admin_email="admin@example.com",
        admin_password="local-secret",
        with_traffic=True,
    )

    result = seed_demo(demo_session, config)
    readings = demo_session.scalars(select(TrafficReading)).all()

    assert result.statuses["traffic_created"] == 4
    assert len(readings) == 4
    assert {reading.lane_id for reading in readings} == set(DEMO_LANE_IDS.values())
    assert {reading.device_id for reading in readings} == {DEMO_DEVICE_ID}
    assert {reading.density for reading in readings} <= {
        TrafficDensity.LOW,
        TrafficDensity.MEDIUM,
    }
    assert {reading.vehicle_count for reading in readings} == {3, 4, 5, 7}


def test_seed_demo_traffic_is_idempotent(
    demo_session: Session,
) -> None:
    config = DemoSeedConfig(
        admin_email="admin@example.com",
        admin_password="local-secret",
        with_traffic=True,
    )

    seed_demo(demo_session, config)
    seed_demo(demo_session, config)

    assert len(demo_session.scalars(select(TrafficReading)).all()) == 4


def test_seed_demo_updates_admin_password_without_printing_or_storing_plaintext(
    demo_session: Session,
) -> None:
    seed_demo(
        demo_session,
        DemoSeedConfig(admin_email="admin@example.com", admin_password="old-secret"),
    )

    result = seed_demo(
        demo_session,
        DemoSeedConfig(admin_email="admin@example.com", admin_password="new-secret"),
    )
    admin = demo_session.scalar(select(User).where(User.email == "admin@example.com"))

    assert result.statuses["updated"] == 1
    assert admin is not None
    assert not verify_password("old-secret", admin.password_hash)
    assert verify_password("new-secret", admin.password_hash)


def test_seed_demo_refuses_production_without_explicit_override() -> None:
    with pytest.raises(SystemExit):
        assert_safe_environment("production", allow_production=False)


def test_seed_demo_allows_production_with_explicit_override() -> None:
    assert_safe_environment("production", allow_production=True)
