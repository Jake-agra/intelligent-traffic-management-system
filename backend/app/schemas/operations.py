from datetime import datetime
import uuid

from pydantic import BaseModel, Field

from app.models.enums import AlertStatus, IncidentStatus, OperatingMode, SignalColor
from app.schemas.traffic_operations import APIModel, AlertResponse, IncidentResponse


class OperationalActionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=255)


class SignalModeRequest(OperationalActionRequest):
    mode: OperatingMode


class SignalOverrideRequest(OperationalActionRequest):
    lane_id: uuid.UUID
    requested_color: SignalColor
    duration_seconds: int = Field(ge=1)


class OperationalActionResponse(APIModel):
    action: str
    audit_log_id: uuid.UUID
    emitted_event: str


class AlertActionResponse(OperationalActionResponse):
    alert: AlertResponse
    status: AlertStatus


class IncidentActionResponse(OperationalActionResponse):
    incident: IncidentResponse
    status: IncidentStatus


class SignalModeResponse(OperationalActionResponse):
    intersection_id: uuid.UUID
    mode: OperatingMode
    reason: str
    status: str = "confirmed"
    command_id: uuid.UUID | None = None


class SignalOverrideResponse(OperationalActionResponse):
    intersection_id: uuid.UUID
    lane_id: uuid.UUID
    color: SignalColor
    duration_seconds: int
    started_at: datetime
    ends_at: datetime
    signal_event_id: uuid.UUID | None = None
    command_id: uuid.UUID | None = None
