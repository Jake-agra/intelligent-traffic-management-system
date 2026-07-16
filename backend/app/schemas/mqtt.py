from datetime import UTC, datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import DeviceStatus, SignalColor, TrafficDensity


class MQTTBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware.")
        return value


class DeviceHeartbeatPayload(MQTTBaseModel):
    device_id: uuid.UUID
    status: DeviceStatus
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    temperature_c: float
    ip_address: str
    software_version: str
    sent_at: datetime


class DeviceTelemetryPayload(MQTTBaseModel):
    device_id: uuid.UUID
    metrics: dict[str, object] = Field(default_factory=dict)
    sent_at: datetime


class TrafficTelemetryPayload(MQTTBaseModel):
    intersection_id: uuid.UUID
    lane_id: uuid.UUID
    vehicle_count: int = Field(ge=0)
    density: TrafficDensity
    average_speed: float | None = Field(default=None, ge=0)
    source: str
    captured_at: datetime


class SignalCommandPayload(MQTTBaseModel):
    command_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    intersection_id: uuid.UUID
    lane_id: uuid.UUID
    signal: SignalColor
    duration_seconds: int = Field(ge=1)
    reason: str
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SignalCommandAckPayload(MQTTBaseModel):
    command_id: uuid.UUID
    intersection_id: uuid.UUID
    lane_id: uuid.UUID
    status: str
    message: str | None = None
    acknowledged_at: datetime
