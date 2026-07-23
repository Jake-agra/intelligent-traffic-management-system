from __future__ import annotations

from collections.abc import Awaitable, Callable
import asyncio
import ssl
from typing import Protocol

from app.config import Settings


MessageHandler = Callable[[str, bytes], Awaitable[None]]
ConnectHandler = Callable[[], Awaitable[None]]


class MQTTClientProtocol(Protocol):
    async def connect(self) -> None:
        ...

    async def disconnect(self) -> None:
        ...

    async def subscribe(self, topic: str) -> None:
        ...

    async def publish(self, topic: str, payload: str) -> None:
        ...

    def set_message_handler(self, handler: MessageHandler) -> None:
        ...

    def set_connect_handler(self, handler: ConnectHandler) -> None:
        ...


class FakeMQTTClient:
    def __init__(self) -> None:
        self.connected = False
        self.subscriptions: list[str] = []
        self.published: list[tuple[str, str]] = []
        self.handler: MessageHandler | None = None
        self.connect_handler: ConnectHandler | None = None

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def subscribe(self, topic: str) -> None:
        self.subscriptions.append(topic)

    async def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))

    def set_message_handler(self, handler: MessageHandler) -> None:
        self.handler = handler

    def set_connect_handler(self, handler: ConnectHandler) -> None:
        self.connect_handler = handler


class PahoMQTTClient:
    def __init__(self, settings: Settings) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise RuntimeError("Install paho-mqtt to enable MQTT support.") from exc

        self._mqtt = mqtt
        self._settings = settings
        self._handler: MessageHandler | None = None
        self._connect_handler: ConnectHandler | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._connected: asyncio.Future[None] | None = None
        self._has_connected_once = False
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
        )
        if settings.mqtt_username:
            self._client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        if settings.mqtt_tls_enabled:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    async def connect(self) -> None:
        self._event_loop = asyncio.get_running_loop()
        self._connected = self._event_loop.create_future()
        self._client.connect_async(
            self._settings.mqtt_broker_host,
            self._settings.mqtt_broker_port,
            self._settings.mqtt_keepalive_seconds,
        )
        self._client.loop_start()
        await asyncio.wait_for(self._connected, timeout=10)

    async def disconnect(self) -> None:
        await asyncio.to_thread(self._client.disconnect)
        self._client.loop_stop()

    async def subscribe(self, topic: str) -> None:
        await asyncio.to_thread(self._client.subscribe, topic)

    async def publish(self, topic: str, payload: str) -> None:
        result = await asyncio.to_thread(self._client.publish, topic, payload)
        if result.rc != self._mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed with code {result.rc}.")

    def set_message_handler(self, handler: MessageHandler) -> None:
        self._handler = handler

    def set_connect_handler(self, handler: ConnectHandler) -> None:
        self._connect_handler = handler

    def _on_connect(
        self,
        _client: object,
        _userdata: object,
        _flags: object,
        reason_code: object,
        _properties: object,
    ) -> None:
        if self._connected is None or self._event_loop is None:
            return
        try:
            connected = int(reason_code) == 0
        except (TypeError, ValueError):
            connected = str(reason_code).lower() == "success"
        if connected:
            if self._connected is not None and not self._connected.done():
                self._event_loop.call_soon_threadsafe(self._connected.set_result, None)
            elif self._has_connected_once and self._connect_handler is not None:
                asyncio.run_coroutine_threadsafe(self._connect_handler(), self._event_loop)
            self._has_connected_once = True
        else:
            error = RuntimeError(f"MQTT connection failed with code {reason_code}.")
            if self._connected is not None and not self._connected.done():
                self._event_loop.call_soon_threadsafe(self._connected.set_exception, error)

    def _on_message(self, _client: object, _userdata: object, message: object) -> None:
        if self._handler is None or self._event_loop is None:
            return
        topic = getattr(message, "topic")
        payload = getattr(message, "payload")
        asyncio.run_coroutine_threadsafe(self._handler(topic, payload), self._event_loop)
