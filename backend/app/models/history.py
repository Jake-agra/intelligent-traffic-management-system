from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import (
    DeviceStatus,
    OperatingMode,
    SignalColor,
    SignalEventSource,
    enum_values,
)
from app.models.mixins import UUIDPrimaryKeyMixin, utc_now


class SignalEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "signal_events"
    __table_args__ = (
        Index("ix_signal_events_intersection_id", "intersection_id"),
        Index("ix_signal_events_lane_id", "lane_id"),
        Index("ix_signal_events_user_id", "user_id"),
        Index("ix_signal_events_source", "source"),
        Index("ix_signal_events_occurred_at", "occurred_at"),
    )

    intersection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intersections.id"),
        nullable=False,
    )
    lane_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lanes.id"))
    previous_color: Mapped[SignalColor] = mapped_column(
        SqlEnum(
            SignalColor,
            name="signal_color",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    new_color: Mapped[SignalColor] = mapped_column(
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
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    source: Mapped[SignalEventSource] = mapped_column(
        SqlEnum(
            SignalEventSource,
            name="signal_event_source",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    intersection: Mapped["Intersection"] = relationship(back_populates="signal_events")
    lane: Mapped["Lane | None"] = relationship(back_populates="signal_events")
    responsible_user: Mapped["User | None"] = relationship(
        back_populates="signal_events"
    )


class DeviceEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "device_events"
    __table_args__ = (
        Index("ix_device_events_device_id", "device_id"),
        Index("ix_device_events_event_type", "event_type"),
        Index("ix_device_events_occurred_at", "occurred_at"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"), nullable=False)
    previous_status: Mapped[DeviceStatus] = mapped_column(
        SqlEnum(
            DeviceStatus,
            name="device_status",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    new_status: Mapped[DeviceStatus] = mapped_column(
        SqlEnum(
            DeviceStatus,
            name="device_status",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    metrics: Mapped[dict[str, object] | None] = mapped_column(JSON)
    message: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    device: Mapped["Device"] = relationship(back_populates="device_events")


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_occurred_at", "occurred_at"),
        Index("ix_audit_logs_resource_lookup", "resource_type", "resource_id"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    before_state: Mapped[dict[str, object] | None] = mapped_column(JSON)
    after_state: Mapped[dict[str, object] | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    user: Mapped["User | None"] = relationship(back_populates="audit_logs")
