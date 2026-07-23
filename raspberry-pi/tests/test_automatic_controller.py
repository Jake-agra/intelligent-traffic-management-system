import asyncio
from datetime import UTC, datetime
import json
import uuid

from app.automatic_controller import AutomaticSignalController, ControlModeManager, fixed_time_phases
from app.config import Settings
from app.mqtt_client import FakeMQTTClient
from app.schemas import CommandAckStatus, ControllerModeCommandPayload, OperatingMode
from app.signal_executor import SignalCommandExecutor
from app.traffic_light import FakeGPIOAdapter, IntersectionController, IntersectionPins, TrafficLightPins


class ImmediateSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class BlockingSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []
        self.event = asyncio.Event()

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        await self.event.wait()


def test_fixed_time_phase_order_and_durations() -> None:
    settings = _settings(
        auto_ns_green_seconds=7,
        auto_ns_yellow_seconds=2,
        auto_ew_green_seconds=8,
        auto_ew_yellow_seconds=3,
        auto_all_red_seconds=1,
    )

    phases = fixed_time_phases(settings)

    assert [phase.name for phase in phases] == [
        "all_red_before_ns",
        "north_south_green",
        "north_south_yellow",
        "all_red_before_ew",
        "east_west_green",
        "east_west_yellow",
    ]
    assert [phase.duration_seconds for phase in phases] == [1, 7, 2, 1, 8, 3]


def test_north_south_phase_outputs_are_complete_and_non_conflicting() -> None:
    async def run() -> None:
        harness = _harness()
        phase = fixed_time_phases(harness["settings"])[1]

        await harness["automatic"].apply_phase(phase)

        _assert_one_light(harness["gpio"], harness["controller"].north.pins, "green")
        _assert_one_light(harness["gpio"], harness["controller"].south.pins, "green")
        _assert_one_light(harness["gpio"], harness["controller"].east.pins, "red")
        _assert_one_light(harness["gpio"], harness["controller"].west.pins, "red")
        report = _published(harness["mqtt"], "/commands/ack")[-1]
        assert report["source"] == "automatic_phase"
        assert report["resulting_signals"]["north"] == "green"

    asyncio.run(run())


def test_east_west_phase_outputs_are_complete_and_non_conflicting() -> None:
    async def run() -> None:
        harness = _harness()
        phase = fixed_time_phases(harness["settings"])[4]

        await harness["automatic"].apply_phase(phase)

        _assert_one_light(harness["gpio"], harness["controller"].north.pins, "red")
        _assert_one_light(harness["gpio"], harness["controller"].south.pins, "red")
        _assert_one_light(harness["gpio"], harness["controller"].east.pins, "green")
        _assert_one_light(harness["gpio"], harness["controller"].west.pins, "green")

    asyncio.run(run())


def test_automatic_start_does_not_create_duplicate_loop() -> None:
    async def run() -> None:
        harness = _harness(sleep=BlockingSleep())

        first = harness["automatic"].start()
        second = harness["automatic"].start()

        assert first is second
        await harness["automatic"].stop()

    asyncio.run(run())


def test_switch_automatic_to_manual_cancels_loop_and_confirms_all_red() -> None:
    async def run() -> None:
        harness = _harness(sleep=BlockingSleep())
        manager = harness["mode_manager"]
        await manager.start()
        assert manager.automatic.active_task is not None

        ack = await manager.handle_mode_command(_mode_command(harness["settings"], OperatingMode.MANUAL))

        assert ack.status == CommandAckStatus.EXECUTED
        assert manager.mode == OperatingMode.MANUAL
        assert manager.automatic.active_task is None
        for light in harness["controller"].lights.values():
            _assert_one_light(harness["gpio"], light.pins, "red")

    asyncio.run(run())


def test_manual_command_rejected_before_mode_confirmation() -> None:
    async def run() -> None:
        harness = _harness()

        assert not harness["mode_manager"].manual_confirmed

    asyncio.run(run())


def test_manual_to_automatic_resume_starts_from_all_red() -> None:
    async def run() -> None:
        harness = _harness(sleep=BlockingSleep(), settings_overrides={"auto_controller_enabled": False})
        manager = harness["mode_manager"]
        assert manager.mode == OperatingMode.MANUAL

        ack = await manager.handle_mode_command(_mode_command(harness["settings"], OperatingMode.AUTOMATIC))

        assert ack.status == CommandAckStatus.EXECUTED
        assert manager.mode == OperatingMode.AUTOMATIC
        reports = _published(harness["mqtt"], "/commands/ack")
        assert any(report["source"] == "automatic_startup" for report in reports)
        await manager.stop()

    asyncio.run(run())


def test_emergency_failsafe_sets_all_red() -> None:
    async def run() -> None:
        harness = _harness()
        harness["controller"].north.show_green()

        await harness["mode_manager"].enter_failsafe(uuid.uuid4(), "GPIO failure")

        assert harness["mode_manager"].mode == OperatingMode.FAILSAFE
        for light in harness["controller"].lights.values():
            _assert_one_light(harness["gpio"], light.pins, "red")
        assert _published(harness["mqtt"], "/controller/status")[-1]["mode"] == "failsafe"

    asyncio.run(run())


def _harness(
    *,
    settings_overrides: dict[str, object] | None = None,
    sleep: ImmediateSleep | BlockingSleep | None = None,
) -> dict[str, object]:
    settings = _settings(**(settings_overrides or {}))
    mqtt = FakeMQTTClient()
    gpio = FakeGPIOAdapter()
    controller = IntersectionController(IntersectionPins.from_settings(settings), gpio)
    executor = SignalCommandExecutor(settings=settings, mqtt_client=mqtt, controller=controller)
    manager = ControlModeManager(
        settings=settings,
        mqtt_client=mqtt,
        controller=controller,
        signal_executor=executor,
        sleep=sleep or ImmediateSleep(),
    )
    automatic = AutomaticSignalController(
        settings=settings,
        controller=controller,
        report_state=executor.publish_current_state,
        report_mode=manager.publish_status,
        sleep=sleep or ImmediateSleep(),
    )
    return {
        "settings": settings,
        "mqtt": mqtt,
        "gpio": gpio,
        "controller": controller,
        "executor": executor,
        "mode_manager": manager,
        "automatic": automatic,
    }


def _settings(**overrides: object) -> Settings:
    lane_ids = {direction: uuid.uuid4() for direction in ("north", "south", "east", "west")}
    values = {
        "device_id": uuid.uuid4(),
        "intersection_id": uuid.uuid4(),
        "traffic_light_north_lane_id": str(lane_ids["north"]),
        "traffic_light_south_lane_id": str(lane_ids["south"]),
        "traffic_light_east_lane_id": str(lane_ids["east"]),
        "traffic_light_west_lane_id": str(lane_ids["west"]),
        "signal_all_red_transition_seconds": 0,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def _mode_command(settings: Settings, mode: OperatingMode) -> ControllerModeCommandPayload:
    return ControllerModeCommandPayload(
        command_id=uuid.uuid4(),
        intersection_id=settings.intersection_id,
        mode=mode,
        reason=f"Switch to {mode.value}",
        issued_at=datetime.now(UTC),
    )


def _published(mqtt: FakeMQTTClient, topic_suffix: str) -> list[dict[str, object]]:
    return [json.loads(payload) for topic, payload in mqtt.published if topic.endswith(topic_suffix)]


def _assert_one_light(gpio: FakeGPIOAdapter, pins: TrafficLightPins, active_colour: str) -> None:
    expected = {
        pins.red: gpio.HIGH if active_colour == "red" else gpio.LOW,
        pins.yellow: gpio.HIGH if active_colour == "yellow" else gpio.LOW,
        pins.green: gpio.HIGH if active_colour == "green" else gpio.LOW,
    }
    for pin, value in expected.items():
        assert gpio.pin_values[pin] == value
