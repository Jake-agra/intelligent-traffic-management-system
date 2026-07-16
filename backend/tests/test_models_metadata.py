from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.models import Base


def test_model_metadata_can_create_all_tables() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "alerts",
        "devices",
        "device_events",
        "incidents",
        "intersections",
        "lanes",
        "audit_logs",
        "signal_events",
        "signal_states",
        "refresh_tokens",
        "traffic_readings",
        "users",
        "violations",
    }
