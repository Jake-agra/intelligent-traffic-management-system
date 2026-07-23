import asyncio
import json
import uuid

from app.config import Settings
from app.main import EdgeService
from app.mqtt_client import FakeMQTTClient
from app.telemetry import StaticTelemetryProvider
from app.traffic_light import FakeGPIOAdapter, IntersectionController, IntersectionPins


def test_graceful_shutdown_path() -> None:
    settings = Settings(
        device_id=uuid.uuid4(),
        intersection_id=uuid.uuid4(),
        mqtt_enabled=True,
        heartbeat_interval_seconds=60,
        telemetry_interval_seconds=60,
        _env_file=None,
    )
    mqtt_client = FakeMQTTClient()
    gpio = FakeGPIOAdapter()
    controller = IntersectionController(IntersectionPins.from_settings(settings), gpio)
    service = EdgeService(
        settings=settings,
        mqtt_client=mqtt_client,
        telemetry_provider=StaticTelemetryProvider(settings),
        intersection_controller=controller,
    )

    asyncio.run(_start_and_stop(service))

    assert mqtt_client.connected is False
    assert mqtt_client.subscriptions == [
        f"itms/v1/intersections/{settings.intersection_id}/commands/signal",
        f"itms/v1/intersections/{settings.intersection_id}/commands/controller-mode",
    ]
    assert all(value == gpio.LOW for value in gpio.pin_values.values())


def test_safe_startup_sets_all_lights_red() -> None:
    settings = _settings()
    mqtt_client = FakeMQTTClient()
    gpio = FakeGPIOAdapter()
    controller = IntersectionController(IntersectionPins.from_settings(settings), gpio)
    service = EdgeService(
        settings=settings,
        mqtt_client=mqtt_client,
        telemetry_provider=StaticTelemetryProvider(settings),
        intersection_controller=controller,
    )

    asyncio.run(_start_assert_all_red_and_stop(service, controller, gpio))


def test_safe_shutdown_sets_all_outputs_off() -> None:
    settings = _settings()
    mqtt_client = FakeMQTTClient()
    gpio = FakeGPIOAdapter()
    controller = IntersectionController(IntersectionPins.from_settings(settings), gpio)
    service = EdgeService(
        settings=settings,
        mqtt_client=mqtt_client,
        telemetry_provider=StaticTelemetryProvider(settings),
        intersection_controller=controller,
    )

    asyncio.run(_start_and_stop(service))

    assert all(value == gpio.LOW for value in gpio.pin_values.values())


def test_startup_publishes_all_red_state_report() -> None:
    settings = _settings()
    mqtt_client = FakeMQTTClient()
    controller = IntersectionController(IntersectionPins.from_settings(settings), FakeGPIOAdapter())
    service = EdgeService(
        settings=settings,
        mqtt_client=mqtt_client,
        telemetry_provider=StaticTelemetryProvider(settings),
        intersection_controller=controller,
    )

    asyncio.run(_start_and_stop(service))

    report = _published_state_reports(mqtt_client)[0]
    assert report["source"] == "startup"
    assert report["resulting_signals"] == {
        "north": "red",
        "south": "red",
        "east": "red",
        "west": "red",
    }


def test_reconnect_publishes_current_state_report() -> None:
    settings = _settings()
    mqtt_client = FakeMQTTClient()
    controller = IntersectionController(IntersectionPins.from_settings(settings), FakeGPIOAdapter())
    service = EdgeService(
        settings=settings,
        mqtt_client=mqtt_client,
        telemetry_provider=StaticTelemetryProvider(settings),
        intersection_controller=controller,
    )

    async def run() -> None:
        await service.start()
        await service.publish_reconnect_state()
        await service.stop()

    asyncio.run(run())

    reports = _published_state_reports(mqtt_client)
    assert [report["source"] for report in reports[:2]] == ["startup", "reconnect"]


async def _start_and_stop(service: EdgeService) -> None:
    await service.start()
    await service.stop()


async def _start_assert_all_red_and_stop(
    service: EdgeService,
    controller: IntersectionController,
    gpio: FakeGPIOAdapter,
) -> None:
    await service.start()
    for light in controller.lights.values():
        assert gpio.pin_values[light.pins.red] == gpio.HIGH
        assert gpio.pin_values[light.pins.yellow] == gpio.LOW
        assert gpio.pin_values[light.pins.green] == gpio.LOW
    await service.stop()


def _settings() -> Settings:
    return Settings(
        device_id=uuid.uuid4(),
        intersection_id=uuid.uuid4(),
        mqtt_enabled=True,
        heartbeat_interval_seconds=60,
        telemetry_interval_seconds=60,
        traffic_light_north_lane_id=str(uuid.uuid4()),
        traffic_light_south_lane_id=str(uuid.uuid4()),
        traffic_light_east_lane_id=str(uuid.uuid4()),
        traffic_light_west_lane_id=str(uuid.uuid4()),
        _env_file=None,
    )


def _published_state_reports(mqtt_client: FakeMQTTClient) -> list[dict[str, object]]:
    reports: list[dict[str, object]] = []
    for topic, payload in mqtt_client.published:
        if topic.endswith("/commands/ack"):
            reports.append(json.loads(payload))
    return reports
