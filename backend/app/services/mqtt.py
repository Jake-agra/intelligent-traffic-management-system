from datetime import UTC, datetime
import json
import logging
import uuid

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.enums import DeviceStatus
from app.models.history import DeviceEvent
from app.models.traffic import TrafficReading
from app.mqtt.client import MQTTClientProtocol
from app.mqtt.topics import inbound_topics, signal_command_topic, topic_kind
from app.realtime import realtime_event_publisher
from app.repositories import mqtt as mqtt_repository
from app.schemas.mqtt import (
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


class MQTTService:
    def __init__(
        self,
        *,
        client: MQTTClientProtocol,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.client = client
        self.session_factory = session_factory
        self._seen_message_keys: set[str] = set()

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

    async def publish_signal_command(self, command: SignalCommandPayload) -> None:
        await self.client.publish(
            signal_command_topic(command.intersection_id),
            command.model_dump_json(),
        )

    async def process_signal_command_ack(
        self,
        payload: SignalCommandAckPayload,
    ) -> None:
        self._reject_stale(payload.acknowledged_at)
        self._dedupe(f"command_ack:{payload.command_id}:{payload.status}")
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
                },
            )
        )

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
