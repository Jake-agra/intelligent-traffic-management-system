from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class SignalColor(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


class OperatingMode(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    FAILSAFE = "failsafe"


class CommandAckStatus(str, Enum):
    ACCEPTED = "accepted"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class EdgeBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def require_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware.")
        return value


class DeviceHeartbeatPayload(EdgeBaseModel):
    device_id: uuid.UUID
    status: DeviceStatus
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    temperature_c: float
    ip_address: str
    software_version: str
    sent_at: datetime


class DeviceTelemetryMetrics(EdgeBaseModel):
    uptime_seconds: float = Field(ge=0)
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    temperature_c: float
    disk_percent: float = Field(ge=0, le=100)
    ip_address: str


class DeviceTelemetryPayload(EdgeBaseModel):
    device_id: uuid.UUID
    metrics: DeviceTelemetryMetrics
    sent_at: datetime


class SignalCommandPayload(EdgeBaseModel):
    command_id: uuid.UUID
    intersection_id: uuid.UUID
    lane_id: uuid.UUID
    signal: SignalColor
    duration_seconds: int = Field(ge=1)
    reason: str
    issued_at: datetime


class SignalCommandAckPayload(EdgeBaseModel):
    command_id: uuid.UUID
    intersection_id: uuid.UUID
    lane_id: uuid.UUID
    status: CommandAckStatus
    message: str
    device_id: uuid.UUID
    requested_signal: SignalColor | None = None
    resulting_signals: dict[str, SignalColor] | None = None
    source: str | None = None
    acknowledged_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("resulting_signals")
    @classmethod
    def validate_resulting_signals(
        cls,
        value: dict[str, SignalColor] | None,
    ) -> dict[str, SignalColor] | None:
        if value is None:
            return None
        expected = {"north", "south", "east", "west"}
        if set(value) != expected:
            raise ValueError("resulting_signals must include north, south, east and west.")
        return value


class ControllerModeCommandPayload(EdgeBaseModel):
    command_id: uuid.UUID
    intersection_id: uuid.UUID
    mode: OperatingMode
    reason: str
    issued_at: datetime


class ControllerModeAckPayload(EdgeBaseModel):
    command_id: uuid.UUID
    intersection_id: uuid.UUID
    status: CommandAckStatus
    mode: OperatingMode
    message: str
    device_id: uuid.UUID
    phase: str | None = None
    phase_started_at: datetime | None = None
    phase_duration_seconds: int | None = Field(default=None, ge=0)
    next_phase: str | None = None
    source: str | None = None
    acknowledged_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
