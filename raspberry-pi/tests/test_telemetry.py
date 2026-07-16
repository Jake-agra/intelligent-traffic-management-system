import uuid

from app.config import Settings
from app.schemas import DeviceStatus
from app.telemetry import StaticTelemetryProvider


def test_heartbeat_payload_generation() -> None:
    settings = _settings()
    provider = StaticTelemetryProvider(settings)

    payload = provider.heartbeat()

    assert payload.device_id == settings.device_id
    assert payload.status == DeviceStatus.ONLINE
    assert payload.cpu_percent == 18.4
    assert payload.memory_percent == 42.1
    assert payload.temperature_c == 51.2
    assert payload.ip_address == "192.168.1.20"
    assert payload.sent_at.tzinfo is not None


def test_telemetry_payload_generation() -> None:
    settings = _settings()
    provider = StaticTelemetryProvider(settings)

    payload = provider.telemetry()

    assert payload.device_id == settings.device_id
    assert payload.metrics.uptime_seconds >= 0
    assert payload.metrics.cpu_percent == 18.4
    assert payload.metrics.memory_percent == 42.1
    assert payload.metrics.temperature_c == 51.2
    assert payload.metrics.disk_percent == 50.0
    assert payload.metrics.ip_address == "192.168.1.20"
    assert payload.sent_at.tzinfo is not None


def _settings() -> Settings:
    return Settings(
        device_id=uuid.uuid4(),
        intersection_id=uuid.uuid4(),
        _env_file=None,
    )
