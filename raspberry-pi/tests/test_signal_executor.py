import asyncio
from datetime import UTC, datetime, timedelta
import json
import uuid

import pytest

from app.command_handler import CommandHandler
from app.config import Settings
from app.mqtt_client import FakeMQTTClient
from app.schemas import CommandAckStatus, SignalColor, SignalCommandPayload
from app.signal_executor import SignalCommandExecutor
from app.traffic_light import FakeGPIOAdapter, IntersectionController, IntersectionPins, TrafficLightPins


class BlockingSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []
        self._event = asyncio.Event()

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if seconds > 0:
            await self._event.wait()


class ImmediateSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class FailingGPIOAdapter(FakeGPIOAdapter):
    def output(self, pin: int, value: object) -> None:
        raise RuntimeError(f"output failed on BCM {pin}")


def test_valid_north_green_execution() -> None:
    async def run() -> None:
        harness = _harness()

        await harness["handler"].handle_message(
            "ignored",
            _command(harness["settings"], "north", SignalColor.GREEN).model_dump_json().encode(),
        )
        await _wait_for_status(harness["mqtt"], CommandAckStatus.EXECUTED)

        _assert_statuses(
            harness["mqtt"],
            [CommandAckStatus.ACCEPTED, CommandAckStatus.EXECUTED],
        )
        _assert_one_light(harness["gpio"], harness["controller"].north.pins, "green")
        _assert_one_light(harness["gpio"], harness["controller"].east.pins, "red")
        _assert_one_light(harness["gpio"], harness["controller"].west.pins, "red")
        await harness["executor"].shutdown_safe_state()

    asyncio.run(run())


def test_valid_south_red_execution() -> None:
    async def run() -> None:
        harness = _harness()

        await harness["handler"].handle_message(
            "ignored",
            _command(harness["settings"], "south", SignalColor.RED).model_dump_json().encode(),
        )
        await _wait_for_status(harness["mqtt"], CommandAckStatus.EXECUTED)

        _assert_one_light(harness["gpio"], harness["controller"].south.pins, "red")
        await harness["executor"].shutdown_safe_state()

    asyncio.run(run())


def test_valid_east_green_execution() -> None:
    async def run() -> None:
        harness = _harness()

        await harness["handler"].handle_message(
            "ignored",
            _command(harness["settings"], "east", SignalColor.GREEN).model_dump_json().encode(),
        )
        await _wait_for_status(harness["mqtt"], CommandAckStatus.EXECUTED)

        _assert_one_light(harness["gpio"], harness["controller"].east.pins, "green")
        _assert_one_light(harness["gpio"], harness["controller"].north.pins, "red")
        _assert_one_light(harness["gpio"], harness["controller"].south.pins, "red")
        await harness["executor"].shutdown_safe_state()

    asyncio.run(run())


def test_valid_west_yellow_execution() -> None:
    async def run() -> None:
        harness = _harness()

        await harness["handler"].handle_message(
            "ignored",
            _command(harness["settings"], "west", SignalColor.YELLOW).model_dump_json().encode(),
        )
        await _wait_for_status(harness["mqtt"], CommandAckStatus.EXECUTED)

        _assert_one_light(harness["gpio"], harness["controller"].west.pins, "yellow")
        await harness["executor"].shutdown_safe_state()

    asyncio.run(run())


def test_unknown_direction_rejection() -> None:
    async def run() -> None:
        harness = _harness()
        command = _command(harness["settings"], "north", SignalColor.GREEN, lane_id=uuid.uuid4())

        ack = await harness["handler"].handle_message("ignored", command.model_dump_json().encode())

        assert ack.status == CommandAckStatus.REJECTED
        assert "not mapped" in ack.message
        _assert_statuses(harness["mqtt"], [CommandAckStatus.REJECTED])

    asyncio.run(run())


def test_wrong_intersection_rejection() -> None:
    async def run() -> None:
        harness = _harness()
        command = _command(
            harness["settings"],
            "north",
            SignalColor.GREEN,
            intersection_id=uuid.uuid4(),
        )

        ack = await harness["handler"].handle_message("ignored", command.model_dump_json().encode())

        assert ack.status == CommandAckStatus.REJECTED
        assert "intersection" in ack.message

    asyncio.run(run())


def test_stale_command_rejection() -> None:
    async def run() -> None:
        harness = _harness(settings_overrides={"command_max_age_seconds": 5})
        command = _command(
            harness["settings"],
            "north",
            SignalColor.GREEN,
            issued_at=datetime.now(UTC) - timedelta(seconds=10),
        )

        ack = await harness["handler"].handle_message("ignored", command.model_dump_json().encode())

        assert ack.status == CommandAckStatus.REJECTED
        assert "stale" in ack.message

    asyncio.run(run())


def test_excessive_duration_rejection() -> None:
    async def run() -> None:
        harness = _harness(settings_overrides={"signal_command_max_duration_seconds": 5})
        command = _command(harness["settings"], "north", SignalColor.GREEN, duration_seconds=6)

        ack = await harness["handler"].handle_message("ignored", command.model_dump_json().encode())

        assert ack.status == CommandAckStatus.REJECTED
        assert "duration" in ack.message

    asyncio.run(run())


def test_conflicting_green_prevention_and_all_red_transition_between_axes() -> None:
    async def run() -> None:
        sleep = ImmediateSleep()
        harness = _harness(sleep=sleep, settings_overrides={"signal_all_red_transition_seconds": 0})
        harness["controller"].north.show_green()

        await harness["handler"].handle_message(
            "ignored",
            _command(harness["settings"], "east", SignalColor.GREEN).model_dump_json().encode(),
        )
        await _wait_for_status(harness["mqtt"], CommandAckStatus.EXECUTED)

        _assert_one_light(harness["gpio"], harness["controller"].north.pins, "red")
        _assert_one_light(harness["gpio"], harness["controller"].south.pins, "red")
        _assert_one_light(harness["gpio"], harness["controller"].east.pins, "red")
        _assert_one_light(harness["gpio"], harness["controller"].west.pins, "red")
        assert (harness["controller"].north.pins.red, harness["gpio"].HIGH) in harness["gpio"].outputs
        assert (harness["controller"].east.pins.green, harness["gpio"].HIGH) in harness["gpio"].outputs

    asyncio.run(run())


def test_successful_accepted_and_executed_acknowledgements() -> None:
    async def run() -> None:
        harness = _harness()

        await harness["handler"].handle_message(
            "ignored",
            _command(harness["settings"], "north", SignalColor.GREEN).model_dump_json().encode(),
        )
        await _wait_for_status(harness["mqtt"], CommandAckStatus.EXECUTED)

        _assert_statuses(
            harness["mqtt"],
            [CommandAckStatus.ACCEPTED, CommandAckStatus.EXECUTED],
        )
        await harness["executor"].shutdown_safe_state()

    asyncio.run(run())


def test_gpio_failure_acknowledgement() -> None:
    async def run() -> None:
        settings = _settings()
        mqtt = FakeMQTTClient()
        gpio = FailingGPIOAdapter()
        controller = IntersectionController(IntersectionPins.from_settings(settings), gpio)
        executor = SignalCommandExecutor(settings=settings, mqtt_client=mqtt, controller=controller)
        handler = CommandHandler(settings, mqtt, executor)

        await handler.handle_message(
            "ignored",
            _command(settings, "north", SignalColor.GREEN).model_dump_json().encode(),
        )
        await _wait_for_status(mqtt, CommandAckStatus.FAILED)

        _assert_statuses(mqtt, [CommandAckStatus.ACCEPTED, CommandAckStatus.FAILED])

    asyncio.run(run())


def test_duplicate_command_handling() -> None:
    async def run() -> None:
        harness = _harness()
        command = _command(harness["settings"], "north", SignalColor.GREEN)
        payload = command.model_dump_json().encode()

        await harness["handler"].handle_message("ignored", payload)
        await harness["handler"].handle_message("ignored", payload)

        _assert_statuses(harness["mqtt"], [CommandAckStatus.ACCEPTED, CommandAckStatus.DUPLICATE])
        await harness["executor"].shutdown_safe_state()

    asyncio.run(run())


def test_active_command_replacement() -> None:
    async def run() -> None:
        harness = _harness()

        await harness["handler"].handle_message(
            "ignored",
            _command(harness["settings"], "north", SignalColor.GREEN).model_dump_json().encode(),
        )
        await _wait_for_status(harness["mqtt"], CommandAckStatus.EXECUTED)
        first_task = harness["executor"].active_task
        assert first_task is not None

        await harness["handler"].handle_message(
            "ignored",
            _command(harness["settings"], "east", SignalColor.GREEN).model_dump_json().encode(),
        )
        await _wait_for_status_count(harness["mqtt"], CommandAckStatus.EXECUTED, 2)

        assert first_task.cancelled()
        _assert_one_light(harness["gpio"], harness["controller"].east.pins, "green")
        _assert_one_light(harness["gpio"], harness["controller"].north.pins, "red")
        await harness["executor"].shutdown_safe_state()

    asyncio.run(run())


def test_fake_gpio_execution() -> None:
    async def run() -> None:
        harness = _harness(settings_overrides={"gpio_enabled": False})

        await harness["handler"].handle_message(
            "ignored",
            _command(harness["settings"], "west", SignalColor.YELLOW).model_dump_json().encode(),
        )
        await _wait_for_status(harness["mqtt"], CommandAckStatus.EXECUTED)

        assert isinstance(harness["gpio"], FakeGPIOAdapter)
        _assert_one_light(harness["gpio"], harness["controller"].west.pins, "yellow")
        await harness["executor"].shutdown_safe_state()

    asyncio.run(run())


def test_no_blocking_sleep_in_mqtt_callback_path() -> None:
    async def run() -> None:
        sleep = BlockingSleep()
        harness = _harness(sleep=sleep)

        await harness["handler"].handle_message(
            "ignored",
            _command(harness["settings"], "north", SignalColor.GREEN).model_dump_json().encode(),
        )

        _assert_statuses(harness["mqtt"], [CommandAckStatus.ACCEPTED])
        assert sleep.calls == []
        await _wait_for_status(harness["mqtt"], CommandAckStatus.EXECUTED)
        assert sleep.calls == [20]
        await harness["executor"].shutdown_safe_state()

    asyncio.run(run())


def _harness(
    *,
    settings_overrides: dict[str, object] | None = None,
    sleep: BlockingSleep | ImmediateSleep | None = None,
) -> dict[str, object]:
    settings = _settings(**(settings_overrides or {}))
    mqtt = FakeMQTTClient()
    gpio = FakeGPIOAdapter()
    controller = IntersectionController(IntersectionPins.from_settings(settings), gpio)
    executor = SignalCommandExecutor(
        settings=settings,
        mqtt_client=mqtt,
        controller=controller,
        sleep=sleep or BlockingSleep(),
    )
    handler = CommandHandler(settings, mqtt, executor)
    return {
        "settings": settings,
        "mqtt": mqtt,
        "gpio": gpio,
        "controller": controller,
        "executor": executor,
        "handler": handler,
    }


def _settings(**overrides: object) -> Settings:
    lane_ids = {
        "north": uuid.uuid4(),
        "south": uuid.uuid4(),
        "east": uuid.uuid4(),
        "west": uuid.uuid4(),
    }
    values = {
        "device_id": uuid.uuid4(),
        "intersection_id": uuid.uuid4(),
        "traffic_light_north_lane_id": str(lane_ids["north"]),
        "traffic_light_south_lane_id": str(lane_ids["south"]),
        "traffic_light_east_lane_id": str(lane_ids["east"]),
        "traffic_light_west_lane_id": str(lane_ids["west"]),
        "signal_command_max_duration_seconds": 30,
        "signal_all_red_transition_seconds": 0,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def _command(
    settings: Settings,
    direction: str,
    signal: SignalColor,
    *,
    command_id: uuid.UUID | None = None,
    intersection_id: uuid.UUID | None = None,
    lane_id: uuid.UUID | None = None,
    duration_seconds: int = 20,
    issued_at: datetime | None = None,
) -> SignalCommandPayload:
    configured_lane = getattr(settings, f"traffic_light_{direction}_lane_id")
    return SignalCommandPayload(
        command_id=command_id or uuid.uuid4(),
        intersection_id=intersection_id or settings.intersection_id,
        lane_id=lane_id or uuid.UUID(str(configured_lane)),
        signal=signal,
        duration_seconds=duration_seconds,
        reason="mqtt_signal_command_test",
        issued_at=issued_at or datetime.now(UTC),
    )


async def _wait_for_status(mqtt: FakeMQTTClient, status: CommandAckStatus) -> None:
    await _wait_for_status_count(mqtt, status, 1)


async def _wait_for_status_count(
    mqtt: FakeMQTTClient,
    status: CommandAckStatus,
    expected_count: int,
) -> None:
    for _ in range(20):
        if _statuses(mqtt).count(status) >= expected_count:
            return
        await asyncio.sleep(0)
    raise AssertionError(f"Timed out waiting for {status.value} acknowledgement")


def _statuses(mqtt: FakeMQTTClient) -> list[CommandAckStatus]:
    return [
        CommandAckStatus(json.loads(payload)["status"])
        for _topic, payload in mqtt.published
    ]


def _assert_statuses(mqtt: FakeMQTTClient, statuses: list[CommandAckStatus]) -> None:
    assert _statuses(mqtt) == statuses


def _assert_one_light(gpio: FakeGPIOAdapter, pins: TrafficLightPins, active_colour: str) -> None:
    expected = {
        pins.red: gpio.HIGH if active_colour == "red" else gpio.LOW,
        pins.yellow: gpio.HIGH if active_colour == "yellow" else gpio.LOW,
        pins.green: gpio.HIGH if active_colour == "green" else gpio.LOW,
    }
    for pin, value in expected.items():
        assert gpio.pin_values[pin] == value
