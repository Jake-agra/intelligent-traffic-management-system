from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
import uuid

from app.config import Settings
from app.mqtt_client import MQTTClientProtocol
from app.schemas import (
    CommandAckStatus,
    SignalColor,
    SignalCommandAckPayload,
    SignalCommandPayload,
)
from app.traffic_light import EAST_WEST, NORTH_SOUTH, IntersectionController


SleepFn = Callable[[float], Awaitable[None]]
ZERO_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")


class SignalCommandExecutor:
    def __init__(
        self,
        *,
        settings: Settings,
        mqtt_client: MQTTClientProtocol,
        controller: IntersectionController,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self.mqtt_client = mqtt_client
        self.controller = controller
        self.sleep = sleep
        self.active_task: asyncio.Task[None] | None = None
        self._logger = logging.getLogger(__name__)

    def startup_safe_state(self) -> None:
        self.controller.set_all_red()
        self._logger.info("Intersection GPIO startup safe state set to all red")

    async def shutdown_safe_state(self) -> None:
        canceled = self.cancel_active_command()
        if canceled is not None:
            await asyncio.gather(canceled, return_exceptions=True)
        self.controller.all_off()
        self._logger.info("Intersection GPIO shutdown safe state set to all off")

    def schedule(self, command: SignalCommandPayload, direction: str) -> asyncio.Task[None]:
        self.cancel_active_command()
        self.active_task = asyncio.create_task(self._execute(command, direction))
        self.active_task.add_done_callback(self._clear_active_task)
        return self.active_task

    def cancel_active_command(self) -> asyncio.Task[None] | None:
        if self.active_task is not None and not self.active_task.done():
            self.active_task.cancel()
            return self.active_task
        return None

    async def _execute(self, command: SignalCommandPayload, direction: str) -> None:
        try:
            await self._apply_command(command, direction)
            await self._publish_ack(
                command,
                CommandAckStatus.EXECUTED,
                f"Executed {command.signal.value} for {direction}.",
                source="gpio",
                include_state=True,
            )
            self._logger.info(
                "Executed signal command %s: direction=%s signal=%s duration=%s",
                command.command_id,
                direction,
                command.signal.value,
                command.duration_seconds,
            )
            await self.sleep(command.duration_seconds)
            self.controller.set_all_red()
            await self.publish_current_state(
                source="timed_restoration",
                command_id=command.command_id,
                lane_id=command.lane_id,
                requested_signal=command.signal,
                message=f"Command {command.command_id} expired; restored all red.",
            )
            self._logger.info("Signal command %s expired; returned to all red", command.command_id)
        except asyncio.CancelledError:
            self._logger.info("Signal command %s was replaced by a newer command", command.command_id)
            raise
        except Exception as exc:
            await self._publish_ack(
                command,
                CommandAckStatus.FAILED,
                f"GPIO execution failed: {exc}",
            )
            self._logger.exception("GPIO execution failed for command %s", command.command_id)

    async def _apply_command(self, command: SignalCommandPayload, direction: str) -> None:
        if command.signal is SignalColor.GREEN:
            await self._prepare_green(direction)
            self._set_opposite_axis_red(direction)

        light = self.controller.light_for(direction)
        if command.signal is SignalColor.RED:
            light.show_red()
        elif command.signal is SignalColor.YELLOW:
            light.show_yellow()
        elif command.signal is SignalColor.GREEN:
            light.show_green()
        else:
            raise ValueError(f"Unsupported signal colour: {command.signal}")

    async def _prepare_green(self, direction: str) -> None:
        if self._opposite_axis_has_green(direction):
            self.controller.set_all_red()
            await self.sleep(self.settings.signal_all_red_transition_seconds)

    def _set_opposite_axis_red(self, direction: str) -> None:
        if direction in NORTH_SOUTH:
            self.controller.east.show_red()
            self.controller.west.show_red()
        elif direction in EAST_WEST:
            self.controller.north.show_red()
            self.controller.south.show_red()

    def _opposite_axis_has_green(self, direction: str) -> bool:
        if direction in NORTH_SOUTH:
            return (
                self.controller.east.active_colour == "green"
                or self.controller.west.active_colour == "green"
            )
        if direction in EAST_WEST:
            return (
                self.controller.north.active_colour == "green"
                or self.controller.south.active_colour == "green"
            )
        return False

    async def _publish_ack(
        self,
        command: SignalCommandPayload,
        status: CommandAckStatus,
        message: str,
        *,
        source: str | None = None,
        include_state: bool = False,
    ) -> None:
        await self.mqtt_client.publish(
            f"itms/v1/intersections/{command.intersection_id}/commands/ack",
            SignalCommandAckPayload(
                command_id=command.command_id,
                intersection_id=command.intersection_id,
                lane_id=command.lane_id,
                status=status,
                message=message,
                device_id=self.settings.device_id,
                requested_signal=command.signal,
                resulting_signals=self.current_signal_state() if include_state else None,
                source=source,
            ).model_dump_json(),
        )

    async def publish_current_state(
        self,
        *,
        source: str,
        command_id: uuid.UUID | None = None,
        lane_id: uuid.UUID | None = None,
        requested_signal: SignalColor | None = None,
        message: str | None = None,
    ) -> None:
        await self.mqtt_client.publish(
            f"itms/v1/intersections/{self.settings.intersection_id}/commands/ack",
            SignalCommandAckPayload(
                command_id=command_id or ZERO_UUID,
                intersection_id=self.settings.intersection_id,
                lane_id=lane_id or ZERO_UUID,
                status=CommandAckStatus.EXECUTED,
                message=message or f"Physical signal state report: {source}.",
                device_id=self.settings.device_id,
                requested_signal=requested_signal,
                resulting_signals=self.current_signal_state(),
                source=source,
            ).model_dump_json(),
        )

    def current_signal_state(self) -> dict[str, SignalColor]:
        result: dict[str, SignalColor] = {}
        for direction, light in self.controller.lights.items():
            colour = light.active_colour or SignalColor.RED.value
            result[direction] = SignalColor(colour)
        return result

    def _clear_active_task(self, task: asyncio.Task[None]) -> None:
        if self.active_task is task:
            self.active_task = None
