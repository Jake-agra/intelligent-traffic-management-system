from __future__ import annotations

from datetime import UTC, datetime
import os
import socket
import time

from app.config import Settings
from app.schemas import (
    DeviceHeartbeatPayload,
    DeviceStatus,
    DeviceTelemetryMetrics,
    DeviceTelemetryPayload,
)


class TelemetryProvider:
    def __init__(self, settings: Settings, *, started_at: float | None = None) -> None:
        self.settings = settings
        self.started_at = started_at or time.monotonic()

    def heartbeat(self) -> DeviceHeartbeatPayload:
        return DeviceHeartbeatPayload(
            device_id=self.settings.device_id,
            status=DeviceStatus.ONLINE,
            cpu_percent=self.cpu_percent(),
            memory_percent=self.memory_percent(),
            temperature_c=self.temperature_c(),
            ip_address=self.ip_address(),
            software_version=self.settings.software_version,
            sent_at=datetime.now(UTC),
        )

    def telemetry(self) -> DeviceTelemetryPayload:
        return DeviceTelemetryPayload(
            device_id=self.settings.device_id,
            metrics=DeviceTelemetryMetrics(
                uptime_seconds=max(0, time.monotonic() - self.started_at),
                cpu_percent=self.cpu_percent(),
                memory_percent=self.memory_percent(),
                temperature_c=self.temperature_c(),
                disk_percent=self.disk_percent(),
                ip_address=self.ip_address(),
            ),
            sent_at=datetime.now(UTC),
        )

    def cpu_percent(self) -> float:
        try:
            load_average = os.getloadavg()[0]
        except (AttributeError, OSError):
            return 0.0
        cpu_count = os.cpu_count() or 1
        return min(100.0, max(0.0, (load_average / cpu_count) * 100))

    def memory_percent(self) -> float:
        try:
            import psutil
        except ImportError:
            return 0.0
        return float(psutil.virtual_memory().percent)

    def disk_percent(self) -> float:
        try:
            import psutil
        except ImportError:
            return 0.0
        return float(psutil.disk_usage("/").percent)

    def temperature_c(self) -> float:
        thermal_path = "/sys/class/thermal/thermal_zone0/temp"
        try:
            with open(thermal_path, encoding="utf-8") as temperature_file:
                return float(temperature_file.read().strip()) / 1000
        except (OSError, ValueError):
            return 0.0

    def ip_address(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("8.8.8.8", 80))
                return str(probe.getsockname()[0])
        except OSError:
            return "127.0.0.1"


class StaticTelemetryProvider(TelemetryProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, started_at=time.monotonic() - 10)

    def cpu_percent(self) -> float:
        return 18.4

    def memory_percent(self) -> float:
        return 42.1

    def disk_percent(self) -> float:
        return 50.0

    def temperature_c(self) -> float:
        return 51.2

    def ip_address(self) -> str:
        return "192.168.1.20"
