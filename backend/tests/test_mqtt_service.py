from collections.abc import Awaitable, Callable
import asyncio
from datetime import UTC, datetime, timedelta
import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models.enums import DeviceStatus, DeviceType, OperatingMode, SignalColor, TrafficDensity
from app.models.history import DeviceEvent, SignalEvent
from app.models.traffic import ControllerState, Device, Intersection, Lane, SignalState, TrafficReading
from app.mqtt.client import MessageHandler
from app.mqtt.topics import signal_command_topic
from app.realtime import websocket_manager
from app.schemas.mqtt import (
    ControllerModeAckPayload,
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


def test_accepted_acknowledgement_does_not_change_confirmed_state(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)

    _run(
        mqtt_service.process_signal_command_ack(
            _ack_payload(context, status="accepted", lane_direction="north")
        )
    )

    assert db_session.scalars(select(SignalState)).all() == []
    assert db_session.scalars(select(SignalEvent)).all() == []


def test_executed_acknowledgement_changes_confirmed_state_and_publishes_event(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)
    websocket = FakeWebSocket()
    _connect_fake_websocket(websocket, events=frozenset([RealtimeEventName.SIGNAL_UPDATED]))

    _run(
        mqtt_service.process_signal_command_ack(
            _ack_payload(
                context,
                status="executed",
                lane_direction="north",
                resulting_signals={
                    "north": SignalColor.GREEN,
                    "south": SignalColor.RED,
                    "east": SignalColor.RED,
                    "west": SignalColor.RED,
                },
            )
        )
    )

    states = db_session.scalars(select(SignalState)).all()
    events = db_session.scalars(select(SignalEvent)).all()
    assert len(states) == 4
    assert len(events) == 4
    assert {
        state.color
        for state in states
        if state.lane_id == context["lane_ids"]["north"]
    } == {SignalColor.GREEN}
    assert websocket.sent[1]["data"]["confirmed"] is True
    assert websocket.sent[1]["data"]["resulting_signals"]["north"] == SignalColor.GREEN.value


@pytest.mark.parametrize("status", ["rejected", "failed"])
def test_rejected_or_failed_acknowledgement_preserves_previous_state(
    db_session: Session,
    mqtt_service: MQTTService,
    status: str,
) -> None:
    context = _create_four_way_mqtt_context(db_session)
    north = context["lanes"]["north"]
    db_session.add(
        SignalState(
            intersection_id=context["intersection"].id,
            lane_id=north.id,
            color=SignalColor.RED,
            operating_mode=OperatingMode.MANUAL,
            started_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    _run(
        mqtt_service.process_signal_command_ack(
            _ack_payload(context, status=status, lane_direction="north")
        )
    )

    states = db_session.scalars(select(SignalState)).all()
    assert len(states) == 1
    assert states[0].color == SignalColor.RED


def test_duplicate_executed_acknowledgement_creates_no_duplicate_history(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)
    payload = _ack_payload(
        context,
        status="executed",
        lane_direction="north",
        resulting_signals={
            "north": SignalColor.GREEN,
            "south": SignalColor.RED,
            "east": SignalColor.RED,
            "west": SignalColor.RED,
        },
    )

    _run(mqtt_service.process_signal_command_ack(payload))
    with pytest.raises(DuplicateMQTTMessage):
        _run(mqtt_service.process_signal_command_ack(payload))

    assert len(db_session.scalars(select(SignalState)).all()) == 4
    assert len(db_session.scalars(select(SignalEvent)).all()) == 4


def test_grouped_confirmed_state_is_persisted_from_physical_report(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)

    _run(
        mqtt_service.process_signal_command_ack(
            _ack_payload(
                context,
                status="executed",
                lane_direction="north",
                resulting_signals={
                    "north": SignalColor.GREEN,
                    "south": SignalColor.GREEN,
                    "east": SignalColor.RED,
                    "west": SignalColor.RED,
                },
            )
        )
    )

    by_lane = {
        state.lane_id: state.color
        for state in db_session.scalars(select(SignalState)).all()
    }
    assert by_lane[context["lane_ids"]["north"]] == SignalColor.GREEN
    assert by_lane[context["lane_ids"]["south"]] == SignalColor.GREEN


def test_timed_restoration_state_reaches_backend(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)
    first = _ack_payload(
        context,
        status="executed",
        lane_direction="east",
        resulting_signals={
            "north": SignalColor.RED,
            "south": SignalColor.RED,
            "east": SignalColor.GREEN,
            "west": SignalColor.RED,
        },
        source="gpio",
    )
    restored = _ack_payload(
        context,
        status="executed",
        lane_direction="east",
        command_id=first.command_id,
        resulting_signals={
            "north": SignalColor.RED,
            "south": SignalColor.RED,
            "east": SignalColor.RED,
            "west": SignalColor.RED,
        },
        source="timed_restoration",
        acknowledged_at=first.acknowledged_at + timedelta(seconds=5),
    )

    _run(mqtt_service.process_signal_command_ack(first))
    _run(mqtt_service.process_signal_command_ack(restored))

    latest_east = db_session.scalar(
        select(SignalState)
        .where(SignalState.lane_id == context["lane_ids"]["east"])
        .order_by(SignalState.started_at.desc())
    )
    assert latest_east is not None
    assert latest_east.color == SignalColor.RED


def test_startup_all_red_state_synchronization_is_idempotent(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)

    _run(
        mqtt_service.process_signal_command_ack(
            _state_report(context, source="startup")
        )
    )
    _run(
        mqtt_service.process_signal_command_ack(
            _state_report(
                context,
                source="reconnect",
                acknowledged_at=datetime.now(UTC) + timedelta(seconds=1),
            )
        )
    )

    assert len(db_session.scalars(select(SignalState)).all()) == 4
    assert len(db_session.scalars(select(SignalEvent)).all()) == 4


def test_invalid_device_state_report_rejected(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)

    with pytest.raises(MQTTProcessingError, match="Unknown device"):
        _run(
            mqtt_service.process_signal_command_ack(
                _state_report(context, device_id=uuid.uuid4())
            )
        )


def test_stale_state_report_rejected(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)

    with pytest.raises(StaleMQTTMessage):
        _run(
            mqtt_service.process_signal_command_ack(
                _state_report(
                    context,
                    acknowledged_at=datetime.now(UTC) - timedelta(minutes=20),
                )
            )
        )


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


def test_controller_mode_accepted_remains_pending(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)

    _run(
        mqtt_service.process_controller_mode_ack(
            _controller_ack(context, status="accepted", mode=OperatingMode.MANUAL)
        )
    )

    state = db_session.scalar(select(ControllerState))
    assert state is not None
    assert state.mode == OperatingMode.MANUAL
    assert state.requested_mode == OperatingMode.MANUAL
    assert state.command_status == "accepted"


def test_controller_mode_executed_becomes_confirmed_and_publishes_event(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)
    websocket = FakeWebSocket()
    _connect_fake_websocket(websocket, events=frozenset([RealtimeEventName.CONTROLLER_MODE_UPDATED]))

    _run(
        mqtt_service.process_controller_mode_ack(
            _controller_ack(
                context,
                status="executed",
                mode=OperatingMode.AUTOMATIC,
                phase="north_south_green",
                next_phase="north_south_yellow",
            )
        )
    )

    state = db_session.scalar(select(ControllerState))
    assert state is not None
    assert state.mode == OperatingMode.AUTOMATIC
    assert state.requested_mode is None
    assert state.command_status == "confirmed"
    assert state.phase == "north_south_green"
    assert websocket.sent[1]["event"] == RealtimeEventName.CONTROLLER_MODE_UPDATED.value


def test_controller_mode_failed_preserves_prior_confirmed_mode(
    db_session: Session,
    mqtt_service: MQTTService,
) -> None:
    context = _create_four_way_mqtt_context(db_session)
    db_session.add(
        ControllerState(
            intersection_id=context["intersection_id"],
            mode=OperatingMode.AUTOMATIC,
            command_status="confirmed",
        )
    )
    db_session.commit()

    _run(
        mqtt_service.process_controller_mode_ack(
            _controller_ack(context, status="failed", mode=OperatingMode.MANUAL)
        )
    )

    state = db_session.scalar(select(ControllerState))
    assert state is not None
    assert state.mode == OperatingMode.AUTOMATIC
    assert state.requested_mode == OperatingMode.MANUAL
    assert state.command_status == "failed"


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


def _create_four_way_mqtt_context(db_session: Session) -> dict[str, object]:
    intersection = Intersection(
        name=f"Four Way MQTT Junction {uuid.uuid4()}",
        location_description="MQTT signal synchronization test",
        is_active=True,
    )
    db_session.add(intersection)
    db_session.flush()

    lanes: dict[str, Lane] = {}
    for sequence, direction in enumerate(("north", "south", "east", "west"), start=1):
        lane = Lane(
            intersection_id=intersection.id,
            name=f"{direction.title()}bound",
            direction=direction,
            sequence=sequence,
            is_active=True,
        )
        db_session.add(lane)
        db_session.flush()
        lanes[direction] = lane

    device = Device(
        intersection_id=intersection.id,
        lane_id=None,
        identifier=f"mqtt-rpi-{uuid.uuid4()}",
        name="MQTT Raspberry Pi",
        type=DeviceType.RASPBERRY_PI,
        status=DeviceStatus.ONLINE,
    )
    db_session.add(device)
    db_session.commit()
    return {
        "intersection": intersection,
        "intersection_id": intersection.id,
        "lanes": lanes,
        "lane_ids": {direction: lane.id for direction, lane in lanes.items()},
        "device": device,
        "device_id": device.id,
    }


def _ack_payload(
    context: dict[str, object],
    *,
    status: str,
    lane_direction: str,
    command_id: uuid.UUID | None = None,
    resulting_signals: dict[str, SignalColor] | None = None,
    source: str | None = None,
    acknowledged_at: datetime | None = None,
) -> SignalCommandAckPayload:
    intersection = context["intersection"]
    lanes = context["lanes"]
    device = context["device"]
    assert isinstance(intersection, Intersection)
    assert isinstance(lanes, dict)
    assert isinstance(device, Device)
    lane = lanes[lane_direction]
    assert isinstance(lane, Lane)
    return SignalCommandAckPayload(
        command_id=command_id or uuid.uuid4(),
        intersection_id=intersection.id,
        lane_id=lane.id,
        status=status,
        message=f"{status} acknowledgement",
        device_id=device.id,
        requested_signal=SignalColor.GREEN,
        resulting_signals=resulting_signals,
        source=source,
        acknowledged_at=acknowledged_at or datetime.now(UTC),
    )


def _state_report(
    context: dict[str, object],
    *,
    source: str = "startup",
    device_id: uuid.UUID | None = None,
    acknowledged_at: datetime | None = None,
) -> SignalCommandAckPayload:
    intersection = context["intersection"]
    device = context["device"]
    assert isinstance(intersection, Intersection)
    assert isinstance(device, Device)
    return SignalCommandAckPayload(
        command_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        intersection_id=intersection.id,
        lane_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        status="executed",
        message=f"{source} report",
        device_id=device_id or device.id,
        resulting_signals={
            "north": SignalColor.RED,
            "south": SignalColor.RED,
            "east": SignalColor.RED,
            "west": SignalColor.RED,
        },
        source=source,
        acknowledged_at=acknowledged_at or datetime.now(UTC),
    )


def _controller_ack(
    context: dict[str, object],
    *,
    status: str,
    mode: OperatingMode,
    phase: str | None = None,
    next_phase: str | None = None,
) -> ControllerModeAckPayload:
    return ControllerModeAckPayload(
        command_id=uuid.uuid4(),
        intersection_id=context["intersection_id"],
        status=status,
        mode=mode,
        message=f"{status} controller mode",
        device_id=context["device_id"],
        phase=phase,
        phase_started_at=datetime.now(UTC) if phase else None,
        phase_duration_seconds=15 if phase else None,
        next_phase=next_phase,
        source="test",
        acknowledged_at=datetime.now(UTC),
    )


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
