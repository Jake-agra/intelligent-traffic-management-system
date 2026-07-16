"""add history traceability models

Revision ID: 0002_add_history_traceability_models
Revises: 0001_create_core_traffic_models
Create Date: 2026-07-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_history_traceability_models"
down_revision: Union[str, None] = "0001_create_core_traffic_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signal_events",
        sa.Column("intersection_id", sa.Uuid(), nullable=False),
        sa.Column("lane_id", sa.Uuid(), nullable=True),
        sa.Column(
            "previous_color",
            sa.Enum("red", "yellow", "green", name="signal_color", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "new_color",
            sa.Enum("red", "yellow", "green", name="signal_color", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "operating_mode",
            sa.Enum("automatic", "manual", name="operating_mode", native_enum=False),
            nullable=False,
        ),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "automatic",
                "manual",
                "emergency",
                "simulation",
                name="signal_event_source",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            name=op.f("fk_signal_events_intersection_id_intersections"),
        ),
        sa.ForeignKeyConstraint(
            ["lane_id"],
            ["lanes.id"],
            name=op.f("fk_signal_events_lane_id_lanes"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_signal_events_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signal_events")),
    )
    op.create_index(
        "ix_signal_events_intersection_id",
        "signal_events",
        ["intersection_id"],
    )
    op.create_index("ix_signal_events_lane_id", "signal_events", ["lane_id"])
    op.create_index("ix_signal_events_occurred_at", "signal_events", ["occurred_at"])
    op.create_index("ix_signal_events_source", "signal_events", ["source"])
    op.create_index("ix_signal_events_user_id", "signal_events", ["user_id"])

    op.create_table(
        "device_events",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column(
            "previous_status",
            sa.Enum(
                "online",
                "offline",
                "degraded",
                name="device_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "new_status",
            sa.Enum(
                "online",
                "offline",
                "degraded",
                name="device_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_device_events_device_id_devices"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_device_events")),
    )
    op.create_index("ix_device_events_device_id", "device_events", ["device_id"])
    op.create_index("ix_device_events_event_type", "device_events", ["event_type"])
    op.create_index("ix_device_events_occurred_at", "device_events", ["occurred_at"])

    op.create_table(
        "audit_logs",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=120), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])
    op.create_index(
        "ix_audit_logs_resource_lookup",
        "audit_logs",
        ["resource_type", "resource_id"],
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_lookup", table_name="audit_logs")
    op.drop_index("ix_audit_logs_occurred_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_device_events_occurred_at", table_name="device_events")
    op.drop_index("ix_device_events_event_type", table_name="device_events")
    op.drop_index("ix_device_events_device_id", table_name="device_events")
    op.drop_table("device_events")

    op.drop_index("ix_signal_events_user_id", table_name="signal_events")
    op.drop_index("ix_signal_events_source", table_name="signal_events")
    op.drop_index("ix_signal_events_occurred_at", table_name="signal_events")
    op.drop_index("ix_signal_events_lane_id", table_name="signal_events")
    op.drop_index("ix_signal_events_intersection_id", table_name="signal_events")
    op.drop_table("signal_events")
