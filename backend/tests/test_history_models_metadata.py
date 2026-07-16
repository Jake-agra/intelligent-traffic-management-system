from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.models import Base


def test_history_model_metadata_includes_traceability_indexes() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    signal_indexes = {index["name"] for index in inspector.get_indexes("signal_events")}
    assert {
        "ix_signal_events_intersection_id",
        "ix_signal_events_lane_id",
        "ix_signal_events_user_id",
        "ix_signal_events_source",
        "ix_signal_events_occurred_at",
    }.issubset(signal_indexes)

    device_indexes = {index["name"] for index in inspector.get_indexes("device_events")}
    assert {
        "ix_device_events_device_id",
        "ix_device_events_event_type",
        "ix_device_events_occurred_at",
    }.issubset(device_indexes)

    audit_indexes = {index["name"] for index in inspector.get_indexes("audit_logs")}
    assert {
        "ix_audit_logs_user_id",
        "ix_audit_logs_action",
        "ix_audit_logs_occurred_at",
        "ix_audit_logs_resource_lookup",
    }.issubset(audit_indexes)
