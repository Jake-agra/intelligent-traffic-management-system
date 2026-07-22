import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app.mqtt import lifecycle


class FakePahoClient:
    def __init__(self, settings) -> None:
        self.settings = settings


class FakeMQTTService:
    instances: list["FakeMQTTService"] = []
    fail_start = False

    def __init__(self, *, client, session_factory) -> None:
        self.client = client
        self.session_factory = session_factory
        self.started = False
        self.stopped = False
        FakeMQTTService.instances.append(self)

    async def start(self) -> None:
        self.started = True
        if self.fail_start:
            raise RuntimeError("startup failed")

    async def stop(self) -> None:
        self.stopped = True


@pytest.fixture(autouse=True)
def reset_fake_service() -> None:
    FakeMQTTService.instances = []
    FakeMQTTService.fail_start = False


def test_mqtt_lifespan_does_not_start_service_when_disabled(monkeypatch) -> None:
    app = FastAPI()
    monkeypatch.setattr(
        lifecycle,
        "get_settings",
        lambda: SimpleNamespace(mqtt_enabled=False),
    )
    monkeypatch.setattr(lifecycle, "MQTTService", FakeMQTTService)

    asyncio.run(_enter_and_exit_lifespan(app))

    assert FakeMQTTService.instances == []
    assert not hasattr(app.state, "mqtt_service")


def test_mqtt_lifespan_starts_stops_and_clears_service(monkeypatch) -> None:
    app = FastAPI()
    monkeypatch.setattr(
        lifecycle,
        "get_settings",
        lambda: SimpleNamespace(mqtt_enabled=True),
    )
    monkeypatch.setattr(lifecycle, "PahoMQTTClient", FakePahoClient)
    monkeypatch.setattr(lifecycle, "MQTTService", FakeMQTTService)

    asyncio.run(_enter_and_exit_lifespan(app))

    service = FakeMQTTService.instances[0]
    assert service.started
    assert service.stopped
    assert not hasattr(app.state, "mqtt_service")


def test_mqtt_lifespan_cleans_up_when_startup_fails(monkeypatch) -> None:
    app = FastAPI()
    FakeMQTTService.fail_start = True
    monkeypatch.setattr(
        lifecycle,
        "get_settings",
        lambda: SimpleNamespace(mqtt_enabled=True),
    )
    monkeypatch.setattr(lifecycle, "PahoMQTTClient", FakePahoClient)
    monkeypatch.setattr(lifecycle, "MQTTService", FakeMQTTService)

    with pytest.raises(RuntimeError, match="startup failed"):
        asyncio.run(_enter_and_exit_lifespan(app))

    service = FakeMQTTService.instances[0]
    assert service.started
    assert service.stopped
    assert not hasattr(app.state, "mqtt_service")


async def _enter_and_exit_lifespan(app: FastAPI) -> None:
    async with lifecycle.mqtt_lifespan(app):
        pass
