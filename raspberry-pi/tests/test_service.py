import asyncio
import uuid

from app.config import Settings
from app.main import EdgeService
from app.mqtt_client import FakeMQTTClient
from app.telemetry import StaticTelemetryProvider


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
    service = EdgeService(
        settings=settings,
        mqtt_client=mqtt_client,
        telemetry_provider=StaticTelemetryProvider(settings),
    )

    asyncio.run(_start_and_stop(service))

    assert mqtt_client.connected is False
    assert mqtt_client.subscriptions == [
        f"itms/v1/intersections/{settings.intersection_id}/commands/signal"
    ]


async def _start_and_stop(service: EdgeService) -> None:
    await service.start()
    await service.stop()
