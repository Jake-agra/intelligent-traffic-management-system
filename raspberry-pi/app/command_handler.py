from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
import uuid

from pydantic import ValidationError

from app.config import Settings
from app.mqtt_client import MQTTClientProtocol
from app.schemas import (
    CommandAckStatus,
    ControllerModeCommandPayload,
    SignalCommandAckPayload,
    SignalCommandPayload,
)
from app.signal_executor import SignalCommandExecutor


logger = logging.getLogger(__name__)


class CommandHandler:
    def __init__(
        self,
        settings: Settings,
        mqtt_client: MQTTClientProtocol,
        executor: SignalCommandExecutor | None = None,
        mode_manager: object | None = None,
    ) -> None:
        self.settings = settings
        self.mqtt_client = mqtt_client
        self.executor = executor
        self.mode_manager = mode_manager
        self._seen_command_ids: set[uuid.UUID] = set()

    async def handle_message(self, topic: str, payload: bytes) -> SignalCommandAckPayload:
        if topic.endswith("/commands/controller-mode"):
            return await self.handle_mode_message(payload)  # type: ignore[return-value]
        try:
            command = SignalCommandPayload.model_validate_json(payload)
            ack, direction = self._validate_command(command)
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

        if ack.status is not CommandAckStatus.ACCEPTED:
            await self.publish_ack(ack)
            return ack

        if command.command_id in self._seen_command_ids:
            ack = self._ack(
                command,
                CommandAckStatus.DUPLICATE,
                "Duplicate command ignored.",
            )
            await self.publish_ack(ack)
            return ack

        self._seen_command_ids.add(command.command_id)
        await self.publish_ack(ack)
        if self.executor is not None:
            self.executor.schedule(command, direction)
        logger.info(
            "Accepted signal command %s for lane=%s direction=%s signal=%s duration=%s",
            command.command_id,
            command.lane_id,
            direction,
            command.signal.value,
            command.duration_seconds,
        )
        return ack

    async def handle_mode_message(self, payload: bytes) -> object:
        try:
            command = ControllerModeCommandPayload.model_validate_json(payload)
        except (ValidationError, ValueError) as exc:
            if self.mode_manager is not None:
                logger.warning("Rejected malformed controller-mode command: %s", exc)
            raise
        if self.mode_manager is None:
            raise RuntimeError("Controller mode manager is not configured.")
        return await self.mode_manager.handle_mode_command(command)

    def handle_command(self, command: SignalCommandPayload) -> SignalCommandAckPayload:
        ack, _direction = self._validate_command(command)
        return ack

    def _validate_command(
        self,
        command: SignalCommandPayload,
    ) -> tuple[SignalCommandAckPayload, str]:
        if command.intersection_id != self.settings.intersection_id:
            return (
                self._ack(
                    command,
                    CommandAckStatus.REJECTED,
                    "Command intersection does not match device context.",
                ),
                "",
            )

        age_seconds = (datetime.now(UTC) - command.issued_at).total_seconds()
        if age_seconds > self.settings.command_max_age_seconds:
            return self._ack(command, CommandAckStatus.REJECTED, "Command is stale."), ""

        duration_limit = min(
            self.settings.signal_command_max_duration_seconds,
            self.settings.manual_override_max_seconds,
        )
        if command.duration_seconds > duration_limit:
            return (
                self._ack(
                    command,
                    CommandAckStatus.REJECTED,
                    "Command duration exceeds configured maximum.",
                ),
                "",
            )

        if self.mode_manager is not None and not self.mode_manager.manual_confirmed:
            return (
                self._ack(
                    command,
                    CommandAckStatus.REJECTED,
                    "Manual mode must be confirmed before manual signal commands.",
                ),
                "",
            )

        direction = self.direction_for_lane(command.lane_id)
        if direction is None:
            return (
                self._ack(
                    command,
                    CommandAckStatus.REJECTED,
                    "Command lane is not mapped to a traffic-light direction.",
                ),
                "",
            )

        return (
            self._ack(
                command,
                CommandAckStatus.ACCEPTED,
                f"Command accepted for {direction}; GPIO execution scheduled.",
            ),
            direction,
        )

    async def publish_ack(self, ack: SignalCommandAckPayload) -> None:
        await self.mqtt_client.publish(
            signal_ack_topic(ack.intersection_id),
            ack.model_dump_json(),
        )

    def direction_for_lane(self, lane_id: uuid.UUID) -> str | None:
        mappings = {
            "north": self.settings.traffic_light_north_lane_id,
            "south": self.settings.traffic_light_south_lane_id,
            "east": self.settings.traffic_light_east_lane_id,
            "west": self.settings.traffic_light_west_lane_id,
        }
        normalized_lane_id = str(lane_id).lower()
        for direction, configured_lane_id in mappings.items():
            if configured_lane_id and configured_lane_id.strip().lower() == normalized_lane_id:
                return direction
        return None

    def _ack(
        self,
        command: SignalCommandPayload,
        status: CommandAckStatus,
        message: str,
    ) -> SignalCommandAckPayload:
        return SignalCommandAckPayload(
            command_id=command.command_id,
            intersection_id=command.intersection_id,
            lane_id=command.lane_id,
            status=status,
            message=message,
            device_id=self.settings.device_id,
        )


def signal_command_topic(intersection_id: object) -> str:
    return f"itms/v1/intersections/{intersection_id}/commands/signal"


def signal_ack_topic(intersection_id: object) -> str:
    return f"itms/v1/intersections/{intersection_id}/commands/ack"


def controller_mode_command_topic(intersection_id: object) -> str:
    return f"itms/v1/intersections/{intersection_id}/commands/controller-mode"


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
