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
    acknowledged_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
