from collections.abc import Awaitable, Callable
import asyncio
from datetime import UTC, datetime, timedelta
import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models.enums import DeviceStatus, DeviceType, SignalColor, TrafficDensity
from app.models.history import DeviceEvent
from app.models.traffic import Device, Intersection, Lane, TrafficReading
from app.mqtt.client import MessageHandler
from app.mqtt.topics import signal_command_topic
from app.realtime import websocket_manager
from app.schemas.mqtt import (
    DeviceHeartbeatPayload,
    SignalCommandAckPayload,
    SignalCommandPayload,
    TrafficTelemetryPayload,
)
from app.schemas.realtime import RealtimeEventName
from app.services.mqtt import (
    DuplicateMQTTMessage,
    MQTTProcessingError,
    MQTTService,
    StaleMQTTMessage,
)


class FakeMQTTClient:
    def __init__(self) -> None:
        self.handler: MessageHandler | None = None
        self.subscriptions: list[str] = []
        self.published: list[tuple[str, str]] = []
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def subscribe(self, topic: str) -> None:
        self.subscriptions.append(topic)

    async def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))

    def set_message_handler(self, handler: MessageHandler) -> None:
        self.handler = handler


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict[str, object]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, object]) -> None:
        self.sent.append(message)


@pytest.fixture(autouse=True)
def reset_realtime_state() -> None:
    websocket_manager.reset()


@pytest.fixture
def fake_client() -> FakeMQTTClient:
    return FakeMQTTClient()


@pytest.fixture
def mqtt_service(
    db_session: Session,
    fake_client: FakeMQTTClient,
) -> MQTTService:
    return MQTTService(client=fake_client, session_factory=_session_factory(db_session))


def test_valid_heartbeat_processing(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_mqtt_context(db_session, status=DeviceStatus.OFFLINE)
    sent_at = datetime.now(UTC)

    _run(
        mqtt_service.process_heartbeat(
            db_session,
            DeviceHeartbeatPayload(
                device_id=context["device"].id,
                status=DeviceStatus.ONLINE,
                cpu_percent=18.4,
                memory_percent=42.1,
                temperature_c=51.2,
                ip_address="192.168.1.20",
                software_version="0.1.0",
                sent_at=sent_at,
            ),
        )
    )

    db_session.refresh(context["device"])
    assert context["device"].status == DeviceStatus.ONLINE
    assert context["device"].last_seen_at == sent_at.replace(tzinfo=None)


def test_unknown_device_is_rejected(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    with pytest.raises(MQTTProcessingError, match="Unknown device"):
        _run(
            mqtt_service.process_heartbeat(
                db_session,
                DeviceHeartbeatPayload(
                    device_id=uuid.uuid4(),
                    status=DeviceStatus.ONLINE,
                    cpu_percent=18.4,
                    memory_percent=42.1,
                    temperature_c=51.2,
                    ip_address="192.168.1.20",
                    software_version="0.1.0",
                    sent_at=datetime.now(UTC),
                ),
            )
        )


def test_device_status_history_creation(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_mqtt_context(db_session, status=DeviceStatus.DEGRADED)

    _run(
        mqtt_service.process_heartbeat(
            db_session,
            DeviceHeartbeatPayload(
                device_id=context["device"].id,
                status=DeviceStatus.ONLINE,
                cpu_percent=10,
                memory_percent=20,
                temperature_c=45,
                ip_address="192.168.1.21",
                software_version="0.1.1",
                sent_at=datetime.now(UTC),
            ),
        )
    )

    device_event = db_session.scalar(
        select(DeviceEvent).where(DeviceEvent.device_id == context["device"].id)
    )
    assert device_event is not None
    assert device_event.event_type == "heartbeat"
    assert device_event.previous_status == DeviceStatus.DEGRADED
    assert device_event.new_status == DeviceStatus.ONLINE


def test_valid_traffic_telemetry(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_mqtt_context(db_session)

    _run(mqtt_service.process_traffic_telemetry(db_session, _traffic_payload(context)))

    reading = db_session.scalar(
        select(TrafficReading).where(
            TrafficReading.intersection_id == context["intersection"].id
        )
    )
    assert reading is not None
    assert reading.lane_id == context["lane"].id
    assert reading.vehicle_count == 12
    assert reading.density == TrafficDensity.MEDIUM


def test_lane_intersection_mismatch_is_rejected(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_mqtt_context(db_session)
    other = _create_mqtt_context(db_session, name="Other MQTT Junction")

    with pytest.raises(MQTTProcessingError, match="Lane does not belong"):
        _run(
            mqtt_service.process_traffic_telemetry(
                db_session,
                _traffic_payload(context, lane_id=other["lane"].id),
            )
        )


def test_stale_telemetry_rejection(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_mqtt_context(db_session)

    with pytest.raises(StaleMQTTMessage):
        _run(
            mqtt_service.process_traffic_telemetry(
                db_session,
                _traffic_payload(
                    context,
                    captured_at=datetime.now(UTC) - timedelta(minutes=20),
                ),
            )
        )


def test_malformed_mqtt_payload_is_logged(
    caplog: pytest.LogCaptureFixture,
    mqtt_service: MQTTService,
) -> None:
    _run(
        mqtt_service.handle_message(
            f"itms/v1/devices/{uuid.uuid4()}/heartbeat",
            b"{not-json",
        )
    )

    assert "Malformed MQTT payload" in caplog.text


def test_duplicate_telemetry_handling(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_mqtt_context(db_session)
    payload = _traffic_payload(context)

    _run(mqtt_service.process_traffic_telemetry(db_session, payload))
    with pytest.raises(DuplicateMQTTMessage):
        _run(mqtt_service.process_traffic_telemetry(db_session, payload))

    readings = db_session.scalars(select(TrafficReading)).all()
    assert len(readings) == 1


def test_signal_command_publication(
    mqtt_service: MQTTService,
    fake_client: FakeMQTTClient,
) -> None:
    intersection_id = uuid.uuid4()
    command = SignalCommandPayload(
        command_id=uuid.uuid4(),
        intersection_id=intersection_id,
        lane_id=uuid.uuid4(),
        signal=SignalColor.GREEN,
        duration_seconds=20,
        reason="adaptive_density_control",
        issued_at=datetime.now(UTC),
    )

    _run(mqtt_service.publish_signal_command(command))

    assert fake_client.published[0][0] == signal_command_topic(intersection_id)
    assert json.loads(fake_client.published[0][1])["signal"] == SignalColor.GREEN.value


def test_command_acknowledgement_publishes_signal_update(
    mqtt_service: MQTTService,
) -> None:
    intersection_id = uuid.uuid4()
    websocket = FakeWebSocket()
    _connect_fake_websocket(
        websocket,
        events=frozenset([RealtimeEventName.SIGNAL_UPDATED]),
    )
    delivered = _run(
        mqtt_service.process_signal_command_ack(
            SignalCommandAckPayload(
                command_id=uuid.uuid4(),
                intersection_id=intersection_id,
                lane_id=uuid.uuid4(),
                status="accepted",
                message="Command queued",
                acknowledged_at=datetime.now(UTC),
            )
        )
    )
    message = websocket.sent[1]

    assert delivered is None
    assert message["event"] == RealtimeEventName.SIGNAL_UPDATED.value
    assert message["intersection_id"] == str(intersection_id)


@pytest.mark.parametrize(
    "status",
    ["accepted", "executed", "rejected", "failed", "duplicate"],
)
def test_phase_11_command_acknowledgement_status_compatibility(
    mqtt_service: MQTTService,
    status: str,
) -> None:
    payload = SignalCommandAckPayload(
        command_id=uuid.uuid4(),
        intersection_id=uuid.uuid4(),
        lane_id=uuid.uuid4(),
        status=status,
        message=f"{status} acknowledgement",
        device_id=uuid.uuid4(),
        acknowledged_at=datetime.now(UTC),
    )

    _run(mqtt_service.process_signal_command_ack(payload))


def test_websocket_publication_from_traffic_telemetry(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_mqtt_context(db_session)
    websocket = FakeWebSocket()

    _connect_fake_websocket(
        websocket,
        events=frozenset([RealtimeEventName.TRAFFIC_UPDATED]),
    )
    delivered = _run(
        mqtt_service.process_traffic_telemetry(
            db_session,
            _traffic_payload(context),
        )
    )
    message = websocket.sent[1]

    assert delivered is None
    assert message["event"] == RealtimeEventName.TRAFFIC_UPDATED.value
    assert message["intersection_id"] == str(context["intersection"].id)


def test_mqtt_disabled_application_startup(client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert not hasattr(app.state, "mqtt_service")


def _session_factory(db_session: Session) -> Callable[[], Session]:
    return lambda: db_session


def _run(awaitable: Awaitable[object]) -> object:
    return asyncio.run(awaitable)


def _connect_fake_websocket(
    websocket: FakeWebSocket,
    *,
    intersection_id: uuid.UUID | None = None,
    events: frozenset[RealtimeEventName] | None = None,
) -> uuid.UUID:
    return _run(
        websocket_manager.connect(
            websocket,
            intersection_id=intersection_id,
            events=events,
        )
    )


def _create_mqtt_context(
    db_session: Session,
    *,
    name: str = "MQTT Junction",
    status: DeviceStatus = DeviceStatus.OFFLINE,
) -> dict[str, object]:
    intersection = Intersection(
        name=f"{name} {uuid.uuid4()}",
        location_description="MQTT telemetry test",
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
        identifier=f"mqtt-device-{uuid.uuid4()}",
        name="MQTT Test Device",
        type=DeviceType.RASPBERRY_PI,
        status=status,
    )
    db_session.add(device)
    db_session.commit()
    return {"intersection": intersection, "lane": lane, "device": device}


def _traffic_payload(
    context: dict[str, object],
    *,
    lane_id: uuid.UUID | None = None,
    captured_at: datetime | None = None,
) -> TrafficTelemetryPayload:
    intersection = context["intersection"]
    lane = context["lane"]
    assert isinstance(intersection, Intersection)
    assert isinstance(lane, Lane)
    return TrafficTelemetryPayload(
        intersection_id=intersection.id,
        lane_id=lane_id or lane.id,
        vehicle_count=12,
        density=TrafficDensity.MEDIUM,
        average_speed=18.5,
        source="camera",
        captured_at=captured_at or datetime.now(UTC),
    )
