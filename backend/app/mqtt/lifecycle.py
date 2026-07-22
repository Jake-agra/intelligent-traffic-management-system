from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.mqtt.client import PahoMQTTClient
from app.services.mqtt import MQTTService


@asynccontextmanager
async def mqtt_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    service: MQTTService | None = None
    if settings.mqtt_enabled:
        service = MQTTService(
            client=PahoMQTTClient(settings),
            session_factory=SessionLocal,
        )
        app.state.mqtt_service = service
        try:
            await service.start()
        except Exception:
            await service.stop()
            if hasattr(app.state, "mqtt_service"):
                del app.state.mqtt_service
            raise
    try:
        yield
    finally:
        if service is not None:
            await service.stop()
            if hasattr(app.state, "mqtt_service"):
                del app.state.mqtt_service
