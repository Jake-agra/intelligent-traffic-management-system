from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import uuid

from app.config import Settings
from app.mqtt_client import MQTTClientProtocol
from app.schemas import (
    CommandAckStatus,
    ControllerModeAckPayload,
    ControllerModeCommandPayload,
    OperatingMode,
)
from app.traffic_light import IntersectionController


SleepFn = Callable[[float], Awaitable[None]]
StateReporter = Callable[..., Awaitable[None]]
ZERO_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")


@dataclass(frozen=True)
class SignalPhase:
    name: str
    duration_seconds: float
    outputs: dict[str, str]
    next_phase: str


def fixed_time_phases(settings: Settings) -> tuple[SignalPhase, ...]:
    return (
        SignalPhase(
            "all_red_before_ns",
            settings.auto_all_red_seconds,
            _all_red(),
            "north_south_green",
        ),
        SignalPhase(
            "north_south_green",
            settings.auto_ns_green_seconds,
            {"north": "green", "south": "green", "east": "red", "west": "red"},
            "north_south_yellow",
        ),
        SignalPhase(
            "north_south_yellow",
            settings.auto_ns_yellow_seconds,
            {"north": "yellow", "south": "yellow", "east": "red", "west": "red"},
            "all_red_before_ew",
        ),
        SignalPhase(
            "all_red_before_ew",
            settings.auto_all_red_seconds,
            _all_red(),
            "east_west_green",
        ),
        SignalPhase(
            "east_west_green",
            settings.auto_ew_green_seconds,
            {"north": "red", "south": "red", "east": "green", "west": "green"},
            "east_west_yellow",
        ),
        SignalPhase(
            "east_west_yellow",
            settings.auto_ew_yellow_seconds,
            {"north": "red", "south": "red", "east": "yellow", "west": "yellow"},
            "all_red_before_ns",
        ),
    )


class AutomaticSignalController:
    def __init__(
        self,
        *,
        settings: Settings,
        controller: IntersectionController,
        report_state: StateReporter,
        report_mode: Callable[..., Awaitable[None]],
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self.controller = controller
        self.report_state = report_state
        self.report_mode = report_mode
        self.sleep = sleep
        self.phases = fixed_time_phases(settings)
        self.active_task: asyncio.Task[None] | None = None
        self.current_phase: SignalPhase | None = None
        self.phase_started_at: datetime | None = None
        self._logger = logging.getLogger(__name__)

    def start(self) -> asyncio.Task[None]:
        if self.active_task is not None and not self.active_task.done():
            return self.active_task
        self.active_task = asyncio.create_task(self._run())
        self.active_task.add_done_callback(self._clear_task)
        return self.active_task

    async def stop(self) -> None:
        if self.active_task is None or self.active_task.done():
            return
        self.active_task.cancel()
        await asyncio.gather(self.active_task, return_exceptions=True)

    async def _run(self) -> None:
        phase_index = 0
        while True:
            phase = self.phases[phase_index]
            await self.apply_phase(phase)
            await self._sleep_monotonic(phase.duration_seconds)
            phase_index = (phase_index + 1) % len(self.phases)

    async def apply_phase(self, phase: SignalPhase) -> None:
        _reject_conflicting_green(phase.outputs)
        self.current_phase = phase
        self.phase_started_at = datetime.now(UTC)
        _apply_outputs(self.controller, phase.outputs)
        await self.report_state(source="automatic_phase", message=f"Automatic phase {phase.name}.")
        await self.report_mode(
            status=CommandAckStatus.EXECUTED,
            mode=OperatingMode.AUTOMATIC,
            command_id=ZERO_UUID,
            message=f"Automatic phase {phase.name}.",
            phase=phase,
            source="automatic_phase",
        )
        self._logger.info("Automatic signal phase applied: %s", phase.name)

    async def _sleep_monotonic(self, seconds: float) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + seconds
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            await self.sleep(remaining)

    def _clear_task(self, task: asyncio.Task[None]) -> None:
        if self.active_task is task:
            self.active_task = None


class ControlModeManager:
    def __init__(
        self,
        *,
        settings: Settings,
        mqtt_client: MQTTClientProtocol,
        controller: IntersectionController,
        signal_executor: object,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self.mqtt_client = mqtt_client
        self.controller = controller
        self.signal_executor = signal_executor
        self.mode = OperatingMode.AUTOMATIC if settings.auto_controller_enabled else OperatingMode.MANUAL
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger(__name__)
        self.automatic = AutomaticSignalController(
            settings=settings,
            controller=controller,
            report_state=signal_executor.publish_current_state,
            report_mode=self.publish_status,
            sleep=sleep,
        )

    @property
    def manual_confirmed(self) -> bool:
        return self.mode is OperatingMode.MANUAL

    async def start(self) -> None:
        await self.publish_status(
            status=CommandAckStatus.EXECUTED,
            mode=self.mode,
            command_id=ZERO_UUID,
            message=f"Controller startup mode is {self.mode.value}.",
            phase=self.automatic.phases[0] if self.mode is OperatingMode.AUTOMATIC else None,
            source="startup",
        )
        if self.mode is OperatingMode.AUTOMATIC:
            self.automatic.start()

    async def stop(self) -> None:
        await self.automatic.stop()

    async def handle_mode_command(
        self,
        command: ControllerModeCommandPayload,
    ) -> ControllerModeAckPayload:
        if command.intersection_id != self.settings.intersection_id:
            return await self._publish_rejected(command, "Mode command intersection does not match.")
        age_seconds = (datetime.now(UTC) - command.issued_at).total_seconds()
        if age_seconds > self.settings.command_max_age_seconds:
            return await self._publish_rejected(command, "Mode command is stale.")

        await self.publish_status(
            status=CommandAckStatus.ACCEPTED,
            mode=command.mode,
            command_id=command.command_id,
            message=f"Controller mode change accepted: {command.mode.value}.",
            source="mode_command",
        )
        async with self._lock:
            try:
                if command.mode is OperatingMode.AUTOMATIC:
                    await self._switch_to_automatic(command)
                elif command.mode is OperatingMode.MANUAL:
                    await self._switch_to_manual(command)
                elif command.mode is OperatingMode.FAILSAFE:
                    await self.enter_failsafe(command.command_id, "Failsafe requested by backend.")
                else:
                    return await self._publish_rejected(command, "Unsupported controller mode.")
            except Exception as exc:
                await self.enter_failsafe(command.command_id, f"Controller mode change failed: {exc}")
                raise

        return await self.publish_status(
            status=CommandAckStatus.EXECUTED,
            mode=self.mode,
            command_id=command.command_id,
            message=f"Controller mode confirmed: {self.mode.value}.",
            phase=self.automatic.current_phase,
            source="mode_command",
        )

    async def _switch_to_manual(self, command: ControllerModeCommandPayload) -> None:
        await self.automatic.stop()
        canceled = self.signal_executor.cancel_active_command()
        if canceled is not None:
            await asyncio.gather(canceled, return_exceptions=True)
        self.controller.set_all_red()
        await self.signal_executor.publish_current_state(
            source="mode_all_red",
            command_id=command.command_id,
            message="Manual mode safe all-red transition confirmed.",
        )
        self.mode = OperatingMode.MANUAL

    async def _switch_to_automatic(self, command: ControllerModeCommandPayload) -> None:
        canceled = self.signal_executor.cancel_active_command()
        if canceled is not None:
            await asyncio.gather(canceled, return_exceptions=True)
        await self.automatic.stop()
        self.controller.set_all_red()
        await self.signal_executor.publish_current_state(
            source="automatic_startup",
            command_id=command.command_id,
            message="Automatic resume starts from all red.",
        )
        self.mode = OperatingMode.AUTOMATIC
        self.automatic.current_phase = None
        self.automatic.phase_started_at = None
        self.automatic.start()

    async def enter_failsafe(
        self,
        command_id: uuid.UUID | None,
        message: str,
    ) -> None:
        await self.automatic.stop()
        canceled = self.signal_executor.cancel_active_command()
        if canceled is not None:
            await asyncio.gather(canceled, return_exceptions=True)
        self.controller.set_all_red()
        self.mode = OperatingMode.FAILSAFE
        await self.signal_executor.publish_current_state(
            source="failsafe",
            command_id=command_id or ZERO_UUID,
            message=message,
        )
        await self.publish_status(
            status=CommandAckStatus.EXECUTED,
            mode=OperatingMode.FAILSAFE,
            command_id=command_id or ZERO_UUID,
            message=message,
            source="failsafe",
        )

    async def publish_status(
        self,
        *,
        status: CommandAckStatus,
        mode: OperatingMode,
        command_id: uuid.UUID,
        message: str,
        phase: SignalPhase | None = None,
        source: str | None = None,
    ) -> ControllerModeAckPayload:
        payload = ControllerModeAckPayload(
            command_id=command_id,
            intersection_id=self.settings.intersection_id,
            status=status,
            mode=mode,
            message=message,
            device_id=self.settings.device_id,
            phase=phase.name if phase else None,
            phase_started_at=self.automatic.phase_started_at if phase else None,
            phase_duration_seconds=int(phase.duration_seconds) if phase else None,
            next_phase=phase.next_phase if phase else None,
            source=source,
        )
        await self.mqtt_client.publish(
            f"itms/v1/intersections/{self.settings.intersection_id}/controller/status",
            payload.model_dump_json(),
        )
        return payload

    async def _publish_rejected(
        self,
        command: ControllerModeCommandPayload,
        message: str,
    ) -> ControllerModeAckPayload:
        return await self.publish_status(
            status=CommandAckStatus.REJECTED,
            mode=command.mode,
            command_id=command.command_id,
            message=message,
            source="mode_command",
        )


def _apply_outputs(controller: IntersectionController, outputs: dict[str, str]) -> None:
    for direction, colour in outputs.items():
        light = controller.light_for(direction)
        if colour == "red":
            light.show_red()
        elif colour == "yellow":
            light.show_yellow()
        elif colour == "green":
            light.show_green()
        else:
            raise ValueError(f"Unsupported phase colour: {colour}")


def _reject_conflicting_green(outputs: dict[str, str]) -> None:
    north_south_green = outputs.get("north") == "green" or outputs.get("south") == "green"
    east_west_green = outputs.get("east") == "green" or outputs.get("west") == "green"
    if north_south_green and east_west_green:
        raise ValueError("Conflicting green phases are not allowed.")


def _all_red() -> dict[str, str]:
    return {"north": "red", "south": "red", "east": "red", "west": "red"}
