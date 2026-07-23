from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
import uuid

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.enums import DeviceStatus, OperatingMode, SignalColor, SignalEventSource
from app.models.history import DeviceEvent, SignalEvent
from app.models.traffic import ControllerState, SignalState, TrafficReading
from app.mqtt.client import MQTTClientProtocol
from app.mqtt.topics import (
    controller_mode_command_topic,
    inbound_topics,
    signal_command_topic,
    topic_kind,
)
from app.realtime import realtime_event_publisher
from app.repositories import mqtt as mqtt_repository
from app.schemas.mqtt import (
    ControllerModeAckPayload,
    ControllerModeCommandPayload,
    DeviceHeartbeatPayload,
    DeviceTelemetryPayload,
    SignalCommandAckPayload,
    SignalCommandPayload,
    TrafficTelemetryPayload,
)
from app.schemas.realtime import RealtimeEventEnvelope, RealtimeEventName


logger = logging.getLogger(__name__)


class MQTTProcessingError(Exception):
    pass


class DuplicateMQTTMessage(Exception):
    pass


class StaleMQTTMessage(Exception):
    pass


@dataclass(frozen=True)
class SignalCommandContext:
    command: SignalCommandPayload
    user_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ControllerModeCommandContext:
    command: ControllerModeCommandPayload
    user_id: uuid.UUID | None = None


class MQTTService:
    def __init__(
        self,
        *,
        client: MQTTClientProtocol,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.client = client
        self.session_factory = session_factory
        self._owns_sessions = isinstance(session_factory, sessionmaker)
        self._seen_message_keys: set[str] = set()
        self._command_context_by_id: dict[uuid.UUID, SignalCommandContext] = {}
        self._mode_context_by_id: dict[uuid.UUID, ControllerModeCommandContext] = {}

    async def start(self) -> None:
        self.client.set_message_handler(self.handle_message)
        await self.client.connect()
        for topic in inbound_topics():
            await self.client.subscribe(topic)

    async def stop(self) -> None:
        await self.client.disconnect()

    async def handle_message(self, topic: str, payload: bytes) -> None:
        try:
            data = json.loads(payload.decode("utf-8"))
            kind = topic_kind(topic)
            if kind == "heartbeat":
                parsed = DeviceHeartbeatPayload.model_validate(data)
                with self.session_factory() as db:
                    await self.process_heartbeat(db, parsed)
            elif kind == "device_telemetry":
                parsed = DeviceTelemetryPayload.model_validate(data)
                with self.session_factory() as db:
                    await self.process_device_telemetry(db, parsed)
            elif kind == "traffic":
                parsed = TrafficTelemetryPayload.model_validate(data)
                with self.session_factory() as db:
                    await self.process_traffic_telemetry(db, parsed)
            elif kind == "command_ack":
                parsed = SignalCommandAckPayload.model_validate(data)
                await self.process_signal_command_ack(parsed)
            elif kind == "controller_status":
                parsed = ControllerModeAckPayload.model_validate(data)
                await self.process_controller_mode_ack(parsed)
            else:
                logger.warning("Unsupported MQTT topic: %s", topic)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
            logger.warning("Malformed MQTT payload on %s: %s", topic, exc)
        except (MQTTProcessingError, DuplicateMQTTMessage, StaleMQTTMessage) as exc:
            logger.warning("Rejected MQTT payload on %s: %s", topic, exc)

    async def process_heartbeat(
        self,
        db: Session,
        payload: DeviceHeartbeatPayload,
    ) -> None:
        self._reject_stale(payload.sent_at)
        self._dedupe(f"heartbeat:{payload.device_id}:{payload.sent_at.isoformat()}")
        device = mqtt_repository.get_device(db, payload.device_id)
        if device is None:
            raise MQTTProcessingError("Unknown device.")

        previous_status = device.status
        device.status = payload.status
        device.last_seen_at = payload.sent_at
        mqtt_repository.add_device_event(
            db,
            DeviceEvent(
                device_id=device.id,
                previous_status=previous_status,
                new_status=payload.status,
                event_type="heartbeat",
                metrics={
                    "cpu_percent": payload.cpu_percent,
                    "memory_percent": payload.memory_percent,
                    "temperature_c": payload.temperature_c,
                    "ip_address": payload.ip_address,
                    "software_version": payload.software_version,
                },
                message="Device heartbeat received",
                occurred_at=payload.sent_at,
            ),
        )
        db.commit()
        if previous_status != payload.status:
            await realtime_event_publisher.publish(
                RealtimeEventEnvelope(
                    event=RealtimeEventName.DEVICE_STATUS_CHANGED,
                    intersection_id=device.intersection_id,
                    data={
                        "device_id": str(device.id),
                        "previous_status": previous_status.value,
                        "new_status": payload.status.value,
                    },
                )
            )

    async def process_device_telemetry(
        self,
        db: Session,
        payload: DeviceTelemetryPayload,
    ) -> None:
        self._reject_stale(payload.sent_at)
        self._dedupe(f"device_telemetry:{payload.device_id}:{payload.sent_at.isoformat()}")
        device = mqtt_repository.get_device(db, payload.device_id)
        if device is None:
            raise MQTTProcessingError("Unknown device.")
        mqtt_repository.add_device_event(
            db,
            DeviceEvent(
                device_id=device.id,
                previous_status=device.status,
                new_status=device.status,
                event_type="telemetry",
                metrics=payload.metrics,
                message="Device telemetry received",
                occurred_at=payload.sent_at,
            ),
        )
        db.commit()

    async def process_traffic_telemetry(
        self,
        db: Session,
        payload: TrafficTelemetryPayload,
    ) -> None:
        self._reject_stale(payload.captured_at)
        self._dedupe(
            "traffic:"
            f"{payload.intersection_id}:{payload.lane_id}:{payload.captured_at.isoformat()}"
        )
        intersection = mqtt_repository.get_intersection(db, payload.intersection_id)
        lane = mqtt_repository.get_lane(db, payload.lane_id)
        if intersection is None:
            raise MQTTProcessingError("Unknown intersection.")
        if lane is None or lane.intersection_id != intersection.id:
            raise MQTTProcessingError("Lane does not belong to intersection.")

        reading = mqtt_repository.add_traffic_reading(
            db,
            TrafficReading(
                intersection_id=payload.intersection_id,
                lane_id=payload.lane_id,
                vehicle_count=payload.vehicle_count,
                density=payload.density,
                captured_at=payload.captured_at,
            ),
        )
        db.commit()
        await realtime_event_publisher.publish(
            RealtimeEventEnvelope(
                event=RealtimeEventName.TRAFFIC_UPDATED,
                intersection_id=payload.intersection_id,
                data={
                    "traffic_reading_id": str(reading.id),
                    "lane_id": str(payload.lane_id),
                    "vehicle_count": payload.vehicle_count,
                    "density": payload.density.value,
                    "average_speed": payload.average_speed,
                    "source": payload.source,
                },
            )
        )

    async def publish_signal_command(
        self,
        command: SignalCommandPayload,
        *,
        user_id: uuid.UUID | None = None,
    ) -> None:
        self._command_context_by_id[command.command_id] = SignalCommandContext(
            command=command,
            user_id=user_id,
        )
        await self.client.publish(
            signal_command_topic(command.intersection_id),
            command.model_dump_json(),
        )

    async def publish_controller_mode_command(
        self,
        command: ControllerModeCommandPayload,
        *,
        user_id: uuid.UUID | None = None,
    ) -> None:
        self._mode_context_by_id[command.command_id] = ControllerModeCommandContext(
            command=command,
            user_id=user_id,
        )
        await self.client.publish(
            controller_mode_command_topic(command.intersection_id),
            command.model_dump_json(),
        )

    async def process_signal_command_ack(
        self,
        payload: SignalCommandAckPayload,
    ) -> None:
        self._reject_stale(payload.acknowledged_at)
        self._dedupe(
            "command_ack:"
            f"{payload.command_id}:{payload.status}:{payload.acknowledged_at.isoformat()}"
        )
        state_changed = False
        if payload.status == "executed" and payload.resulting_signals is not None:
            candidate = self.session_factory()
            if isinstance(candidate, Session):
                try:
                    state_changed = self._persist_confirmed_signal_state(candidate, payload)
                finally:
                    if self._owns_sessions:
                        candidate.close()
            else:
                with candidate as db:
                    if db is not None:
                        state_changed = self._persist_confirmed_signal_state(db, payload)
        await realtime_event_publisher.publish(
            RealtimeEventEnvelope(
                event=RealtimeEventName.SIGNAL_UPDATED,
                intersection_id=payload.intersection_id,
                data={
                    "command_id": str(payload.command_id),
                    "lane_id": str(payload.lane_id),
                    "status": payload.status,
                    "message": payload.message,
                    "device_id": str(payload.device_id) if payload.device_id else None,
                    "requested_signal": payload.requested_signal.value
                    if payload.requested_signal
                    else None,
                    "resulting_signals": {
                        direction: signal.value
                        for direction, signal in payload.resulting_signals.items()
                    }
                    if payload.resulting_signals
                    else None,
                    "source": payload.source,
                    "confirmed": payload.status == "executed",
                    "state_changed": state_changed,
                    "acknowledged_at": payload.acknowledged_at.isoformat(),
                },
            )
        )

    async def process_controller_mode_ack(
        self,
        payload: ControllerModeAckPayload,
    ) -> None:
        self._reject_stale(payload.acknowledged_at)
        self._dedupe(
            "controller_status:"
            f"{payload.command_id}:{payload.status}:{payload.acknowledged_at.isoformat()}"
        )
        confirmed = payload.status == "executed"
        state_changed = False
        candidate = self.session_factory()
        if isinstance(candidate, Session):
            try:
                state_changed = self._persist_controller_state(candidate, payload)
            finally:
                if self._owns_sessions:
                    candidate.close()
        else:
            with candidate as db:
                if db is not None:
                    state_changed = self._persist_controller_state(db, payload)
        await realtime_event_publisher.publish(
            RealtimeEventEnvelope(
                event=RealtimeEventName.CONTROLLER_MODE_UPDATED,
                intersection_id=payload.intersection_id,
                data={
                    "command_id": str(payload.command_id),
                    "status": payload.status,
                    "mode": payload.mode.value,
                    "message": payload.message,
                    "device_id": str(payload.device_id) if payload.device_id else None,
                    "phase": payload.phase,
                    "phase_started_at": payload.phase_started_at.isoformat()
                    if payload.phase_started_at
                    else None,
                    "phase_duration_seconds": payload.phase_duration_seconds,
                    "next_phase": payload.next_phase,
                    "source": payload.source,
                    "confirmed": confirmed,
                    "state_changed": state_changed,
                    "acknowledged_at": payload.acknowledged_at.isoformat(),
                },
            )
        )

    def _persist_confirmed_signal_state(
        self,
        db: Session,
        payload: SignalCommandAckPayload,
    ) -> bool:
        intersection = mqtt_repository.get_intersection(db, payload.intersection_id)
        if intersection is None:
            raise MQTTProcessingError("Unknown intersection.")
        if payload.device_id is not None:
            device = mqtt_repository.get_device(db, payload.device_id)
            if device is None:
                raise MQTTProcessingError("Unknown device.")
            if device.intersection_id != intersection.id:
                raise MQTTProcessingError("Device does not belong to intersection.")

        lanes = mqtt_repository.get_lanes_for_intersection(db, payload.intersection_id)
        lanes_by_direction = {lane.direction.lower(): lane for lane in lanes}
        context = self._command_context_by_id.get(payload.command_id)
        operating_mode = _operating_mode_for_signal_report(payload)
        state_changed = False
        for direction, color in (payload.resulting_signals or {}).items():
            lane = lanes_by_direction.get(direction)
            if lane is None:
                raise MQTTProcessingError(f"No lane configured for direction {direction}.")
            latest = mqtt_repository.get_latest_signal_state(
                db,
                intersection_id=payload.intersection_id,
                lane_id=lane.id,
            )
            previous_color = latest.color if latest else SignalColor.RED
            if latest is not None and latest.color == color:
                continue
            signal_state = mqtt_repository.add_signal_state(
                db,
                SignalState(
                    intersection_id=payload.intersection_id,
                    lane_id=lane.id,
                    color=color,
                    operating_mode=operating_mode,
                    started_at=payload.acknowledged_at,
                    ends_at=None,
                ),
            )
            mqtt_repository.add_signal_event(
                db,
                SignalEvent(
                    intersection_id=payload.intersection_id,
                    lane_id=lane.id,
                    previous_color=previous_color,
                    new_color=color,
                    operating_mode=operating_mode,
                    duration_seconds=context.command.duration_seconds if context else 0,
                    reason=_confirmed_signal_reason(payload, context),
                    user_id=context.user_id if context else None,
                    source=SignalEventSource.PHYSICAL,
                    occurred_at=payload.acknowledged_at,
                ),
            )
            state_changed = state_changed or bool(signal_state.id)
        db.commit()
        return state_changed

    def _persist_controller_state(
        self,
        db: Session,
        payload: ControllerModeAckPayload,
    ) -> bool:
        intersection = mqtt_repository.get_intersection(db, payload.intersection_id)
        if intersection is None:
            raise MQTTProcessingError("Unknown intersection.")
        if payload.device_id is not None:
            device = mqtt_repository.get_device(db, payload.device_id)
            if device is None:
                raise MQTTProcessingError("Unknown device.")
            if device.intersection_id != intersection.id:
                raise MQTTProcessingError("Device does not belong to intersection.")

        context = self._mode_context_by_id.get(payload.command_id)
        state = mqtt_repository.get_controller_state(db, payload.intersection_id)
        if state is None:
            state = mqtt_repository.add_controller_state(
                db,
                ControllerState(
                    intersection_id=payload.intersection_id,
                    mode=OperatingMode.MANUAL,
                ),
            )
        before = _controller_snapshot(state)
        state.device_id = payload.device_id
        state.command_id = payload.command_id
        state.command_status = "confirmed" if payload.status == "executed" else payload.status
        state.message = payload.message
        state.reason = context.command.reason if context else payload.source
        state.updated_by_id = context.user_id if context else state.updated_by_id
        if payload.status == "accepted":
            state.requested_mode = payload.mode
        elif payload.status == "executed":
            state.mode = payload.mode
            state.requested_mode = None
            state.phase = payload.phase
            state.phase_started_at = payload.phase_started_at
            state.phase_duration_seconds = payload.phase_duration_seconds
            state.next_phase = payload.next_phase
            state.confirmed_at = payload.acknowledged_at
        elif payload.status in {"failed", "rejected", "duplicate"}:
            state.requested_mode = payload.mode
        db.commit()
        return before != _controller_snapshot(state)

    def _reject_stale(self, timestamp: datetime) -> None:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        age_seconds = (datetime.now(UTC) - timestamp).total_seconds()
        if age_seconds > get_settings().mqtt_max_telemetry_age_seconds:
            raise StaleMQTTMessage("Telemetry is stale.")

    def _dedupe(self, key: str) -> None:
        if key in self._seen_message_keys:
            raise DuplicateMQTTMessage("Duplicate MQTT message.")
        self._seen_message_keys.add(key)


def _confirmed_signal_reason(
    payload: SignalCommandAckPayload,
    context: SignalCommandContext | None,
) -> str:
    if context is not None:
        return context.command.reason
    if payload.source:
        return f"physical_{payload.source}"
    return payload.message or "physical_signal_confirmation"


def _operating_mode_for_signal_report(payload: SignalCommandAckPayload) -> OperatingMode:
    if payload.source in {"automatic_phase", "automatic_startup", "automatic_reconnect"}:
        return OperatingMode.AUTOMATIC
    if payload.source == "failsafe":
        return OperatingMode.FAILSAFE
    return OperatingMode.MANUAL


def _controller_snapshot(state: ControllerState) -> tuple[object, ...]:
    return (
        state.mode,
        state.requested_mode,
        state.command_status,
        state.command_id,
        state.phase,
        state.phase_started_at,
        state.phase_duration_seconds,
        state.next_phase,
        state.device_id,
    )
