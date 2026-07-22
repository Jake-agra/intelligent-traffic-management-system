from __future__ import annotations

import asyncio
import logging
import signal

from app.command_handler import CommandHandler, signal_command_topic
from app.config import Settings
from app.mqtt_client import FakeMQTTClient, MQTTClientProtocol, PahoMQTTClient
from app.signal_executor import SignalCommandExecutor
from app.telemetry import TelemetryProvider
from app.traffic_light import IntersectionController, create_intersection_controller


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


class EdgeService:
    def __init__(
        self,
        *,
        settings: Settings,
        mqtt_client: MQTTClientProtocol | None = None,
        telemetry_provider: TelemetryProvider | None = None,
        intersection_controller: IntersectionController | None = None,
        signal_executor: SignalCommandExecutor | None = None,
    ) -> None:
        self.settings = settings
        self.mqtt_client = mqtt_client or (
            PahoMQTTClient(settings) if settings.mqtt_enabled else FakeMQTTClient()
        )
        self.telemetry_provider = telemetry_provider or TelemetryProvider(settings)
        self.intersection_controller = intersection_controller or create_intersection_controller(
            settings,
            fake=not settings.gpio_enabled,
        )
        self.signal_executor = signal_executor or SignalCommandExecutor(
            settings=settings,
            mqtt_client=self.mqtt_client,
            controller=self.intersection_controller,
        )
        self.command_handler = CommandHandler(settings, self.mqtt_client, self.signal_executor)
        self._tasks: list[asyncio.Task[None]] = []
        self._logger = logging.getLogger(__name__)

    async def start(self) -> None:
        self.signal_executor.startup_safe_state()
        self.mqtt_client.set_message_handler(self.command_handler.handle_message)
        if self.settings.mqtt_enabled:
            await self.mqtt_client.connect()
            await self.mqtt_client.subscribe(signal_command_topic(self.settings.intersection_id))
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._telemetry_loop()),
        ]
        self._logger.info("Raspberry Pi edge service started")

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.signal_executor.shutdown_safe_state()
        await self.mqtt_client.disconnect()
        self._logger.info("Raspberry Pi edge service stopped")

    async def _heartbeat_loop(self) -> None:
        while True:
            await self.publish_heartbeat()
            await asyncio.sleep(self.settings.heartbeat_interval_seconds)

    async def _telemetry_loop(self) -> None:
        while True:
            await self.publish_telemetry()
            await asyncio.sleep(self.settings.telemetry_interval_seconds)

    async def publish_heartbeat(self) -> None:
        payload = self.telemetry_provider.heartbeat()
        await self.mqtt_client.publish(
            f"itms/v1/devices/{self.settings.device_id}/heartbeat",
            payload.model_dump_json(),
        )

    async def publish_telemetry(self) -> None:
        payload = self.telemetry_provider.telemetry()
        await self.mqtt_client.publish(
            f"itms/v1/devices/{self.settings.device_id}/telemetry",
            payload.model_dump_json(),
        )


async def run() -> None:
    settings = Settings()
    configure_logging(settings)
    service = EdgeService(settings=settings)
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop_event.set)
        except NotImplementedError:
            pass

    await service.start()
    try:
        await stop_event.wait()
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(run())
