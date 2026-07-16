from datetime import UTC, datetime
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import (
    AlertSeverity,
    AlertStatus,
    DeviceStatus,
    DeviceType,
    IncidentStatus,
    OperatingMode,
    SignalColor,
    TrafficDensity,
)


class APIModel(BaseModel):
    @field_validator("*", mode="after")
    @classmethod
    def ensure_timezone(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class ORMModel(APIModel):
    model_config = ConfigDict(from_attributes=True)


class LaneResponse(ORMModel):
    id: uuid.UUID
    intersection_id: uuid.UUID
    name: str
    direction: str
    sequence: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class IntersectionSummaryResponse(ORMModel):
    id: uuid.UUID
    name: str
    location_description: str | None
    latitude: float | None
    longitude: float | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class IntersectionDetailResponse(IntersectionSummaryResponse):
    lanes: list[LaneResponse]


class TrafficReadingResponse(ORMModel):
    id: uuid.UUID
    intersection_id: uuid.UUID
    lane_id: uuid.UUID | None
    device_id: uuid.UUID | None
    vehicle_count: int
    density: TrafficDensity
    captured_at: datetime


class SignalStateResponse(ORMModel):
    id: uuid.UUID
    intersection_id: uuid.UUID
    lane_id: uuid.UUID | None
    color: SignalColor
    operating_mode: OperatingMode
    started_at: datetime
    ends_at: datetime | None


class IncidentResponse(ORMModel):
    id: uuid.UUID
    intersection_id: uuid.UUID
    lane_id: uuid.UUID | None
    device_id: uuid.UUID | None
    title: str
    description: str | None
    status: IncidentStatus
    reported_at: datetime
    resolved_at: datetime | None


class ViolationResponse(ORMModel):
    id: uuid.UUID
    intersection_id: uuid.UUID
    lane_id: uuid.UUID | None
    device_id: uuid.UUID | None
    violation_type: str
    evidence_uri: str | None
    occurred_at: datetime


class AlertResponse(ORMModel):
    id: uuid.UUID
    intersection_id: uuid.UUID
    lane_id: uuid.UUID | None
    device_id: uuid.UUID | None
    incident_id: uuid.UUID | None
    title: str
    message: str | None
    severity: AlertSeverity
    status: AlertStatus
    acknowledged_at: datetime | None
    resolved_at: datetime | None


class DeviceHealthResponse(ORMModel):
    id: uuid.UUID
    intersection_id: uuid.UUID
    lane_id: uuid.UUID | None
    identifier: str
    name: str
    type: DeviceType
    status: DeviceStatus
    last_seen_at: datetime | None


class IntersectionLiveResponse(APIModel):
    intersection: IntersectionSummaryResponse
    lanes: list[LaneResponse]
    latest_traffic_readings: list[TrafficReadingResponse]
    current_signal_states: list[SignalStateResponse]
    active_incidents: list[IncidentResponse]
    recent_violations: list[ViolationResponse]
    active_alerts: list[AlertResponse]
    devices: list[DeviceHealthResponse]
    generated_at: datetime


class DashboardSummaryResponse(APIModel):
    generated_at: datetime
    intersections: dict[str, int]
    traffic: dict[str, int | datetime | None]
    signals: dict[str, int]
    incidents: dict[str, int]
    violations: dict[str, int]
    alerts: dict[str, int]
    devices: dict[str, int]
