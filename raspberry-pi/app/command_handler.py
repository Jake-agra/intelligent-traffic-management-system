from __future__ import annotations

from datetime import UTC, datetime
import json
import uuid

from pydantic import ValidationError

from app.config import Settings
from app.mqtt_client import MQTTClientProtocol
from app.schemas import (
    CommandAckStatus,
    SignalCommandAckPayload,
    SignalCommandPayload,
)


class CommandHandler:
    def __init__(self, settings: Settings, mqtt_client: MQTTClientProtocol) -> None:
        self.settings = settings
        self.mqtt_client = mqtt_client

    async def handle_message(self, topic: str, payload: bytes) -> SignalCommandAckPayload:
        try:
            command = SignalCommandPayload.model_validate_json(payload)
            ack = self.handle_command(command)
        except (ValidationError, ValueError) as exc:
            ack = SignalCommandAckPayload(
                command_id=_command_id_from_payload(payload),
                intersection_id=self.settings.intersection_id,
                lane_id=_lane_id_from_payload(payload),
                status=CommandAckStatus.REJECTED,
                message=f"Rejected command: {exc}",
                device_id=self.settings.device_id,
            )
        await self.publish_ack(ack)
        return ack

    def handle_command(self, command: SignalCommandPayload) -> SignalCommandAckPayload:
        if command.intersection_id != self.settings.intersection_id:
            return self._rejected(command, "Command intersection does not match device context.")

        age_seconds = (datetime.now(UTC) - command.issued_at).total_seconds()
        if age_seconds > self.settings.command_max_age_seconds:
            return self._rejected(command, "Command is stale.")

        return SignalCommandAckPayload(
            command_id=command.command_id,
            intersection_id=command.intersection_id,
            lane_id=command.lane_id,
            status=CommandAckStatus.ACCEPTED,
            message="Command accepted; GPIO execution is not enabled in this phase.",
            device_id=self.settings.device_id,
        )

    async def publish_ack(self, ack: SignalCommandAckPayload) -> None:
        await self.mqtt_client.publish(
            signal_ack_topic(ack.intersection_id),
            ack.model_dump_json(),
        )

    def _rejected(
        self,
        command: SignalCommandPayload,
        message: str,
    ) -> SignalCommandAckPayload:
        return SignalCommandAckPayload(
            command_id=command.command_id,
            intersection_id=command.intersection_id,
            lane_id=command.lane_id,
            status=CommandAckStatus.REJECTED,
            message=message,
            device_id=self.settings.device_id,
        )


def signal_command_topic(intersection_id: object) -> str:
    return f"itms/v1/intersections/{intersection_id}/commands/signal"


def signal_ack_topic(intersection_id: object) -> str:
    return f"itms/v1/intersections/{intersection_id}/commands/ack"


def _command_id_from_payload(payload: bytes) -> uuid.UUID:
    try:
        data = json.loads(payload.decode("utf-8"))
        return uuid.UUID(str(data.get("command_id")))
    except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return uuid.UUID("00000000-0000-0000-0000-000000000000")


def _lane_id_from_payload(payload: bytes) -> uuid.UUID:
    try:
        data = json.loads(payload.decode("utf-8"))
        return uuid.UUID(str(data.get("lane_id")))
    except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return uuid.UUID("00000000-0000-0000-0000-000000000000")
