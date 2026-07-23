from datetime import UTC, datetime
from enum import Enum
import uuid

from pydantic import BaseModel, Field, field_validator


class RealtimeEventName(str, Enum):
    TRAFFIC_UPDATED = "traffic.updated"
    SIGNAL_UPDATED = "signal.updated"
    VIOLATION_CREATED = "violation.created"
    INCIDENT_CREATED = "incident.created"
    INCIDENT_UPDATED = "incident.updated"
    ALERT_CREATED = "alert.created"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    DEVICE_STATUS_CHANGED = "device.status_changed"
    CONTROLLER_MODE_UPDATED = "controller.mode_updated"


class RealtimeBaseModel(BaseModel):
    @field_validator("*", mode="after")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class RealtimeEventEnvelope(RealtimeBaseModel):
    event: RealtimeEventName
    version: int = Field(default=1, ge=1)
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    intersection_id: uuid.UUID | None = None
    data: dict[str, object] = Field(default_factory=dict)


class SubscriptionResponse(BaseModel):
    intersection_id: uuid.UUID | None
    events: list[RealtimeEventName] | None


class ConnectionAckEnvelope(RealtimeBaseModel):
    type: str = "connection.acknowledged"
    version: int = 1
    connection_id: uuid.UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    subscription: SubscriptionResponse
    supported_events: list[RealtimeEventName]


class HeartbeatEnvelope(RealtimeBaseModel):
    type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
