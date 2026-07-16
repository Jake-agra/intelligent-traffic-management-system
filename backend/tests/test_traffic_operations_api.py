from datetime import UTC, datetime, timedelta
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import (
    AlertSeverity,
    AlertStatus,
    DeviceStatus,
    DeviceType,
    IncidentStatus,
    OperatingMode,
    SignalColor,
    TrafficDensity,
)
from app.models.traffic import (
    Alert,
    Device,
    Incident,
    Intersection,
    Lane,
    SignalState,
    TrafficReading,
    Violation,
)


def test_dashboard_summary_returns_shared_operational_counts(
    client: TestClient,
    db_session: Session,
) -> None:
    intersection = _create_live_fixture(db_session)

    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["intersections"] == {"total": 1, "active": 1}
    assert body["traffic"]["total_readings"] == 1
    assert body["traffic"]["latest_reading_at"].endswith("Z")
    assert body["signals"] == {"current_states": 1}
    assert body["incidents"] == {"active": 1, "total": 1}
    assert body["violations"] == {"recent": 1, "total": 1}
    assert body["alerts"] == {"active": 1, "total": 1}
    assert body["devices"] == {
        "total": 1,
        "online": 1,
        "offline": 0,
        "degraded": 0,
    }
    assert str(intersection.id)


def test_intersection_live_state_returns_synchronized_payload(
    client: TestClient,
    db_session: Session,
) -> None:
    intersection = _create_live_fixture(db_session)

    response = client.get(f"/api/v1/intersections/{intersection.id}/live")

    assert response.status_code == 200
    body = response.json()
    assert body["intersection"]["id"] == str(intersection.id)
    assert len(body["lanes"]) == 1
    assert len(body["latest_traffic_readings"]) == 1
    assert len(body["current_signal_states"]) == 1
    assert len(body["active_incidents"]) == 1
    assert len(body["recent_violations"]) == 1
    assert len(body["active_alerts"]) == 1
    assert len(body["devices"]) == 1
    assert body["generated_at"].endswith("Z")


def test_alerts_endpoint_returns_paginated_alerts(
    client: TestClient,
    db_session: Session,
) -> None:
    intersection = _create_live_fixture(db_session)

    response = client.get(
        "/api/v1/alerts",
        params={
            "intersection_id": str(intersection.id),
            "status": AlertStatus.OPEN.value,
            "limit": 1,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == AlertStatus.OPEN.value


def test_invalid_intersection_id_returns_not_found(
    client: TestClient,
) -> None:
    response = client.get(f"/api/v1/intersections/{uuid.uuid4()}/live")

    assert response.status_code == 404
    assert response.json() == {"detail": "Intersection not found."}


def _create_live_fixture(db_session: Session) -> Intersection:
    now = datetime.now(UTC)
    intersection = Intersection(
        name="Central Junction",
        location_description="Main road and market street",
        latitude=5.6037,
        longitude=-0.187,
        is_active=True,
    )
    db_session.add(intersection)
    db_session.flush()

    lane = Lane(
        intersection_id=intersection.id,
        name="Northbound",
        direction="north",
        sequence=1,
        is_active=True,
    )
    db_session.add(lane)
    db_session.flush()

    device = Device(
        intersection_id=intersection.id,
        lane_id=lane.id,
        identifier="camera-central-001",
        name="Central Camera",
        type=DeviceType.CAMERA,
        status=DeviceStatus.ONLINE,
        last_seen_at=now,
    )
    db_session.add(device)
    db_session.flush()

    db_session.add(
        TrafficReading(
            intersection_id=intersection.id,
            lane_id=lane.id,
            device_id=device.id,
            vehicle_count=12,
            density=TrafficDensity.MEDIUM,
            captured_at=now,
        )
    )
    db_session.add(
        SignalState(
            intersection_id=intersection.id,
            lane_id=lane.id,
            color=SignalColor.GREEN,
            operating_mode=OperatingMode.AUTOMATIC,
            started_at=now - timedelta(seconds=30),
            ends_at=now + timedelta(seconds=30),
        )
    )
    db_session.add(
        Incident(
            intersection_id=intersection.id,
            lane_id=lane.id,
            device_id=device.id,
            title="Minor obstruction",
            description="Vehicle stopped near the lane edge.",
            status=IncidentStatus.OPEN,
            reported_at=now - timedelta(minutes=5),
        )
    )
    db_session.add(
        Violation(
            intersection_id=intersection.id,
            lane_id=lane.id,
            device_id=device.id,
            violation_type="red_light",
            evidence_uri="s3://traffic-evidence/red-light-001.jpg",
            occurred_at=now - timedelta(minutes=2),
        )
    )
    db_session.add(
        Alert(
            intersection_id=intersection.id,
            lane_id=lane.id,
            device_id=device.id,
            title="High attention required",
            message="Operator review requested.",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.OPEN,
        )
    )
    db_session.commit()
    db_session.refresh(intersection)
    return intersection
