from datetime import UTC, datetime
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    AlertSeverity,
    AlertStatus,
    IncidentStatus,
    OperatingMode,
    SignalColor,
    UserRole,
)
from app.models.history import AuditLog, SignalEvent
from app.models.traffic import Alert, ControllerState, Incident, Intersection, Lane, SignalState
from app.realtime import websocket_manager
from app.schemas.realtime import RealtimeEventName
from tests.conftest import auth_headers_for, create_test_user


def test_alert_acknowledgement(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(db_session, email="ack-admin@example.com", role=UserRole.ADMIN)

    response = client.post(
        f"/api/v1/alerts/{context['alert'].id}/acknowledge",
        json={"reason": "Operator accepted alert"},
        headers=auth_headers_for(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == AlertStatus.ACKNOWLEDGED.value
    assert body["alert"]["acknowledged_at"] is not None


def test_repeated_alert_acknowledgement_is_idempotent(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(db_session, email="repeat-police@example.com", role=UserRole.POLICE)
    url = f"/api/v1/alerts/{context['alert'].id}/acknowledge"

    first = client.post(url, json={"reason": "First ack"}, headers=auth_headers_for(user))
    second = client.post(url, json={"reason": "Repeat ack"}, headers=auth_headers_for(user))

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == AlertStatus.ACKNOWLEDGED.value


def test_alert_resolution(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(db_session, email="resolve-admin@example.com", role=UserRole.ADMIN)

    response = client.post(
        f"/api/v1/alerts/{context['alert'].id}/resolve",
        json={"reason": "Alert cleared"},
        headers=auth_headers_for(user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == AlertStatus.RESOLVED.value


def test_incident_acknowledgement(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(
        db_session,
        email="incident-ack@example.com",
        role=UserRole.EMERGENCY_RESPONDER,
    )

    response = client.post(
        f"/api/v1/incidents/{context['incident'].id}/acknowledge",
        json={"reason": "Responder dispatched"},
        headers=auth_headers_for(user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == IncidentStatus.INVESTIGATING.value


def test_incident_response(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(
        db_session,
        email="incident-respond@example.com",
        role=UserRole.EMERGENCY_RESPONDER,
    )

    response = client.post(
        f"/api/v1/incidents/{context['incident'].id}/respond",
        json={"reason": "Response team on site"},
        headers=auth_headers_for(user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == IncidentStatus.INVESTIGATING.value


def test_incident_resolution(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(
        db_session,
        email="incident-resolve@example.com",
        role=UserRole.EMERGENCY_RESPONDER,
    )

    response = client.post(
        f"/api/v1/incidents/{context['incident'].id}/resolve",
        json={"reason": "Incident cleared"},
        headers=auth_headers_for(user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == IncidentStatus.RESOLVED.value


def test_invalid_incident_transition(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session, incident_status=IncidentStatus.RESOLVED)
    user = create_test_user(db_session, email="invalid-transition@example.com", role=UserRole.ADMIN)

    response = client.post(
        f"/api/v1/incidents/{context['incident'].id}/respond",
        json={"reason": "Cannot respond"},
        headers=auth_headers_for(user),
    )

    assert response.status_code == 409


def test_admin_signal_mode_change(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(db_session, email="mode-admin@example.com", role=UserRole.ADMIN)

    response = client.post(
        f"/api/v1/intersections/{context['intersection'].id}/signal-mode",
        json={"mode": "manual", "reason": "Manual traffic operation"},
        headers=auth_headers_for(user),
    )

    assert response.status_code == 200
    assert response.json()["mode"] == OperatingMode.MANUAL.value


def test_signal_mode_with_mqtt_publishes_controller_command_and_marks_pending(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(db_session, email="mqtt-mode-admin@example.com", role=UserRole.ADMIN)
    fake_mqtt = FakeMQTTService()
    monkeypatch.setattr(
        "app.services.operations.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "max_signal_override_seconds": 180,
                "manual_override_max_seconds": 60,
                "mqtt_enabled": True,
            },
        )(),
    )
    client.app.state.mqtt_service = fake_mqtt

    try:
        response = client.post(
            f"/api/v1/intersections/{context['intersection'].id}/signal-mode",
            json={"mode": "automatic", "reason": "Resume fixed cycle"},
            headers=auth_headers_for(user),
        )
    finally:
        del client.app.state.mqtt_service

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["command_id"]
    assert len(fake_mqtt.mode_commands) == 1
    state = db_session.scalar(select(ControllerState))
    assert state is not None
    assert state.requested_mode == OperatingMode.AUTOMATIC
    assert state.command_status == "pending"


def test_admin_signal_override(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session, initial_signal=SignalColor.RED)
    user = create_test_user(db_session, email="override-admin@example.com", role=UserRole.ADMIN)

    response = client.post(
        f"/api/v1/intersections/{context['intersection'].id}/signal-override",
        json={
            "lane_id": str(context["lane"].id),
            "requested_color": "green",
            "duration_seconds": 30,
            "reason": "Clear emergency route",
        },
        headers=auth_headers_for(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["color"] == SignalColor.GREEN.value
    assert body["signal_event_id"]


def test_admin_signal_override_with_mqtt_publishes_command_without_confirmed_state(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _create_context(db_session, initial_signal=SignalColor.RED)
    user = create_test_user(db_session, email="mqtt-override-admin@example.com", role=UserRole.ADMIN)
    db_session.add(
        ControllerState(
            intersection_id=context["intersection"].id,
            mode=OperatingMode.MANUAL,
            command_status="confirmed",
        )
    )
    db_session.commit()
    fake_mqtt = FakeMQTTService()
    monkeypatch.setattr(
        "app.services.operations.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "max_signal_override_seconds": 180,
                "manual_override_max_seconds": 60,
                "mqtt_enabled": True,
            },
        )(),
    )
    client.app.state.mqtt_service = fake_mqtt

    try:
        response = client.post(
            f"/api/v1/intersections/{context['intersection'].id}/signal-override",
            json={
                "lane_id": str(context["lane"].id),
                "requested_color": "green",
                "duration_seconds": 30,
                "reason": "Publish to physical controller",
            },
            headers=auth_headers_for(user),
        )
    finally:
        del client.app.state.mqtt_service

    assert response.status_code == 200
    body = response.json()
    assert body["command_id"]
    assert body["signal_event_id"] is None
    assert len(fake_mqtt.commands) == 1
    assert fake_mqtt.commands[0].signal == SignalColor.GREEN
    assert fake_mqtt.user_ids == [user.id]
    states = db_session.scalars(select(SignalState)).all()
    assert len(states) == 1
    assert states[0].color == SignalColor.RED


def test_invalid_lane(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(db_session, email="invalid-lane@example.com", role=UserRole.ADMIN)

    response = client.post(
        f"/api/v1/intersections/{context['intersection'].id}/signal-override",
        json={
            "lane_id": str(uuid.uuid4()),
            "requested_color": "green",
            "duration_seconds": 30,
            "reason": "Invalid lane",
        },
        headers=auth_headers_for(user),
    )

    assert response.status_code == 404


def test_unsafe_signal_request(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session, initial_signal=SignalColor.GREEN)
    user = create_test_user(db_session, email="unsafe-admin@example.com", role=UserRole.ADMIN)

    response = client.post(
        f"/api/v1/intersections/{context['intersection'].id}/signal-override",
        json={
            "lane_id": str(context["lane"].id),
            "requested_color": "red",
            "duration_seconds": 30,
            "reason": "Unsafe",
        },
        headers=auth_headers_for(user),
    )

    assert response.status_code == 409


def test_override_duration_limit(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session, initial_signal=SignalColor.RED)
    user = create_test_user(db_session, email="duration-admin@example.com", role=UserRole.ADMIN)

    response = client.post(
        f"/api/v1/intersections/{context['intersection'].id}/signal-override",
        json={
            "lane_id": str(context["lane"].id),
            "requested_color": "green",
            "duration_seconds": 999,
            "reason": "Too long",
        },
        headers=auth_headers_for(user),
    )

    assert response.status_code == 409


def test_analyst_mutation_denied(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(db_session, email="mutation-analyst@example.com", role=UserRole.ANALYST)

    response = client.post(
        f"/api/v1/alerts/{context['alert'].id}/acknowledge",
        json={"reason": "Read only"},
        headers=auth_headers_for(user),
    )

    assert response.status_code == 403


def test_audit_log_creation(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(db_session, email="audit-admin@example.com", role=UserRole.ADMIN)

    response = client.post(
        f"/api/v1/alerts/{context['alert'].id}/acknowledge",
        json={"reason": "Audit this"},
        headers=auth_headers_for(user),
    )

    assert response.status_code == 200
    audit_count = db_session.scalar(select(AuditLog).where(AuditLog.user_id == user.id))
    assert audit_count is not None
    assert audit_count.action == "alert.acknowledge"


def test_signal_event_creation(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session, initial_signal=SignalColor.RED)
    user = create_test_user(db_session, email="signal-event-admin@example.com", role=UserRole.ADMIN)

    response = client.post(
        f"/api/v1/intersections/{context['intersection'].id}/signal-override",
        json={
            "lane_id": str(context["lane"].id),
            "requested_color": "yellow",
            "duration_seconds": 20,
            "reason": "Create history",
        },
        headers=auth_headers_for(user),
    )

    assert response.status_code == 200
    signal_event = db_session.get(SignalEvent, uuid.UUID(response.json()["signal_event_id"]))
    assert signal_event is not None
    assert signal_event.user_id == user.id


def test_websocket_event_publication(
    client: TestClient,
    db_session: Session,
) -> None:
    context = _create_context(db_session)
    user = create_test_user(db_session, email="ws-admin@example.com", role=UserRole.ADMIN)
    websocket = FakeWebSocket()

    client.portal.call(
        websocket_manager.connect,
        websocket,
        intersection_id=None,
        events=frozenset([RealtimeEventName.ALERT_ACKNOWLEDGED]),
    )
    response = client.post(
        f"/api/v1/alerts/{context['alert'].id}/acknowledge",
        json={"reason": "Publish"},
        headers=auth_headers_for(user),
    )
    message = websocket.sent[1]

    assert response.status_code == 200
    assert message["event"] == RealtimeEventName.ALERT_ACKNOWLEDGED.value
    assert message["intersection_id"] == str(context["intersection"].id)


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict[str, object]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, object]) -> None:
        self.sent.append(message)


class FakeMQTTService:
    def __init__(self) -> None:
        self.commands: list[object] = []
        self.mode_commands: list[object] = []
        self.user_ids: list[uuid.UUID | None] = []

    async def publish_signal_command(self, command: object, *, user_id: uuid.UUID | None = None) -> None:
        self.commands.append(command)
        self.user_ids.append(user_id)

    async def publish_controller_mode_command(
        self,
        command: object,
        *,
        user_id: uuid.UUID | None = None,
    ) -> None:
        self.mode_commands.append(command)
        self.user_ids.append(user_id)


def _create_context(
    db_session: Session,
    *,
    initial_signal: SignalColor = SignalColor.RED,
    incident_status: IncidentStatus = IncidentStatus.OPEN,
) -> dict[str, object]:
    now = datetime.now(UTC)
    intersection = Intersection(
        name=f"Operations Junction {uuid.uuid4()}",
        location_description="Operations test intersection",
        is_active=True,
    )
    db_session.add(intersection)
    db_session.flush()

    lane = Lane(
        intersection_id=intersection.id,
        name="Eastbound",
        direction="east",
        sequence=1,
        is_active=True,
    )
    db_session.add(lane)
    db_session.flush()

    alert = Alert(
        intersection_id=intersection.id,
        lane_id=lane.id,
        title="Traffic alert",
        message="Queue forming",
        severity=AlertSeverity.WARNING,
        status=AlertStatus.OPEN,
    )
    incident = Incident(
        intersection_id=intersection.id,
        lane_id=lane.id,
        title="Traffic incident",
        description="Blocked lane",
        status=incident_status,
        reported_at=now,
        resolved_at=now if incident_status == IncidentStatus.RESOLVED else None,
    )
    signal_state = SignalState(
        intersection_id=intersection.id,
        lane_id=lane.id,
        color=initial_signal,
        operating_mode=OperatingMode.AUTOMATIC,
        started_at=now,
    )
    db_session.add_all([alert, incident, signal_state])
    db_session.commit()
    return {
        "intersection": intersection,
        "lane": lane,
        "alert": alert,
        "incident": incident,
        "signal_state": signal_state,
    }
