from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import (
    AlertSeverity,
    AlertStatus,
    DeviceStatus,
    DeviceType,
    IncidentStatus,
    OperatingMode,
    SignalColor,
    TrafficDensity,
    enum_values,
)
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utc_now


if TYPE_CHECKING:
    from app.models.user import User


class Intersection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "intersections"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    location_description: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    lanes: Mapped[list["Lane"]] = relationship(
        back_populates="intersection",
        cascade="all, delete-orphan",
    )
    devices: Mapped[list["Device"]] = relationship(back_populates="intersection")
    traffic_readings: Mapped[list["TrafficReading"]] = relationship(
        back_populates="intersection"
    )
    signal_states: Mapped[list["SignalState"]] = relationship(
        back_populates="intersection"
    )
    violations: Mapped[list["Violation"]] = relationship(back_populates="intersection")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="intersection")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="intersection")


class Lane(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lanes"
    __table_args__ = (
        UniqueConstraint("intersection_id", "name", name="uq_lanes_intersection_name"),
        Index("ix_lanes_intersection_id", "intersection_id"),
    )

    intersection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("intersections.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    direction: Mapped[str] = mapped_column(String(40), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    intersection: Mapped[Intersection] = relationship(back_populates="lanes")
    devices: Mapped[list["Device"]] = relationship(back_populates="lane")
    traffic_readings: Mapped[list["TrafficReading"]] = relationship(back_populates="lane")
    signal_states: Mapped[list["SignalState"]] = relationship(back_populates="lane")
    violations: Mapped[list["Violation"]] = relationship(back_populates="lane")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="lane")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="lane")


class Device(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (
        Index("ix_devices_intersection_id", "intersection_id"),
        Index("ix_devices_status", "status"),
    )

    intersection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("intersections.id"),
        nullable=False,
    )
    lane_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lanes.id"),
    )
    identifier: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[DeviceType] = mapped_column(
        SqlEnum(
            DeviceType,
            name="device_type",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[DeviceStatus] = mapped_column(
        SqlEnum(
            DeviceStatus,
            name="device_status",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=DeviceStatus.OFFLINE,
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    intersection: Mapped[Intersection] = relationship(back_populates="devices")
    lane: Mapped[Lane | None] = relationship(back_populates="devices")
    traffic_readings: Mapped[list["TrafficReading"]] = relationship(back_populates="device")
    violations: Mapped[list["Violation"]] = relationship(back_populates="device")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="device")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="device")


class TrafficReading(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "traffic_readings"
    __table_args__ = (
        Index("ix_traffic_readings_intersection_id", "intersection_id"),
        Index("ix_traffic_readings_captured_at", "captured_at"),
    )

    intersection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("intersections.id"),
        nullable=False,
    )
    lane_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lanes.id"),
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id"),
    )
    vehicle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    density: Mapped[TrafficDensity] = mapped_column(
        SqlEnum(
            TrafficDensity,
            name="traffic_density",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    intersection: Mapped[Intersection] = relationship(back_populates="traffic_readings")
    lane: Mapped[Lane | None] = relationship(back_populates="traffic_readings")
    device: Mapped[Device | None] = relationship(back_populates="traffic_readings")


class SignalState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "signal_states"
    __table_args__ = (
        Index("ix_signal_states_intersection_id", "intersection_id"),
        Index("ix_signal_states_started_at", "started_at"),
    )

    intersection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("intersections.id"),
        nullable=False,
    )
    lane_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lanes.id"),
    )
    color: Mapped[SignalColor] = mapped_column(
        SqlEnum(
            SignalColor,
            name="signal_color",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    operating_mode: Mapped[OperatingMode] = mapped_column(
        SqlEnum(
            OperatingMode,
            name="operating_mode",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    intersection: Mapped[Intersection] = relationship(back_populates="signal_states")
    lane: Mapped[Lane | None] = relationship(back_populates="signal_states")


class Violation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "violations"
    __table_args__ = (
        Index("ix_violations_intersection_id", "intersection_id"),
        Index("ix_violations_occurred_at", "occurred_at"),
    )

    intersection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("intersections.id"),
        nullable=False,
    )
    lane_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lanes.id"),
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id"),
    )
    violation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_uri: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    intersection: Mapped[Intersection] = relationship(back_populates="violations")
    lane: Mapped[Lane | None] = relationship(back_populates="violations")
    device: Mapped[Device | None] = relationship(back_populates="violations")


class Incident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_intersection_id", "intersection_id"),
        Index("ix_incidents_reported_at", "reported_at"),
        Index("ix_incidents_status", "status"),
    )

    intersection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("intersections.id"),
        nullable=False,
    )
    lane_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lanes.id"),
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id"),
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[IncidentStatus] = mapped_column(
        SqlEnum(
            IncidentStatus,
            name="incident_status",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=IncidentStatus.OPEN,
        nullable=False,
    )
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    intersection: Mapped[Intersection] = relationship(back_populates="incidents")
    lane: Mapped[Lane | None] = relationship(back_populates="incidents")
    device: Mapped[Device | None] = relationship(back_populates="incidents")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="incident")


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_intersection_id", "intersection_id"),
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_severity", "severity"),
    )

    intersection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("intersections.id"),
        nullable=False,
    )
    lane_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lanes.id"),
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.id"),
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id"),
    )
    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[AlertSeverity] = mapped_column(
        SqlEnum(
            AlertSeverity,
            name="alert_severity",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[AlertStatus] = mapped_column(
        SqlEnum(
            AlertStatus,
            name="alert_status",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=AlertStatus.OPEN,
        nullable=False,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    intersection: Mapped[Intersection] = relationship(back_populates="alerts")
    lane: Mapped[Lane | None] = relationship(back_populates="alerts")
    device: Mapped[Device | None] = relationship(back_populates="alerts")
    incident: Mapped[Incident | None] = relationship(back_populates="alerts")
    acknowledged_by: Mapped["User | None"] = relationship(
        back_populates="acknowledged_alerts"
    )
