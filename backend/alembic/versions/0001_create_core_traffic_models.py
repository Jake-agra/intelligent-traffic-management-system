"""create core traffic models

Revision ID: 0001_create_core_traffic_models
Revises:
Create Date: 2026-07-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_create_core_traffic_models"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "intersections",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("location_description", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intersections")),
        sa.UniqueConstraint("name", name=op.f("uq_intersections_name")),
    )
    op.create_index(op.f("ix_intersections_created_at"), "intersections", ["created_at"])

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "admin",
                "operator",
                "viewer",
                name="user_role",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_created_at"), "users", ["created_at"])
    op.create_index(op.f("ix_users_email"), "users", ["email"])
    op.create_index(op.f("ix_users_role"), "users", ["role"])

    op.create_table(
        "lanes",
        sa.Column("intersection_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("direction", sa.String(length=40), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            name=op.f("fk_lanes_intersection_id_intersections"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lanes")),
        sa.UniqueConstraint(
            "intersection_id",
            "name",
            name="uq_lanes_intersection_name",
        ),
    )
    op.create_index(op.f("ix_lanes_created_at"), "lanes", ["created_at"])
    op.create_index("ix_lanes_intersection_id", "lanes", ["intersection_id"])

    op.create_table(
        "devices",
        sa.Column("intersection_id", sa.Uuid(), nullable=False),
        sa.Column("lane_id", sa.Uuid(), nullable=True),
        sa.Column("identifier", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "camera",
                "raspberry_pi",
                "traffic_light",
                "buzzer",
                "mqtt_gateway",
                name="device_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "online",
                "offline",
                "degraded",
                name="device_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            name=op.f("fk_devices_intersection_id_intersections"),
        ),
        sa.ForeignKeyConstraint(
            ["lane_id"],
            ["lanes.id"],
            name=op.f("fk_devices_lane_id_lanes"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        sa.UniqueConstraint("identifier", name=op.f("uq_devices_identifier")),
    )
    op.create_index(op.f("ix_devices_created_at"), "devices", ["created_at"])
    op.create_index("ix_devices_intersection_id", "devices", ["intersection_id"])
    op.create_index("ix_devices_status", "devices", ["status"])

    op.create_table(
        "signal_states",
        sa.Column("intersection_id", sa.Uuid(), nullable=False),
        sa.Column("lane_id", sa.Uuid(), nullable=True),
        sa.Column(
            "color",
            sa.Enum("red", "yellow", "green", name="signal_color", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "operating_mode",
            sa.Enum(
                "automatic",
                "manual",
                name="operating_mode",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            name=op.f("fk_signal_states_intersection_id_intersections"),
        ),
        sa.ForeignKeyConstraint(
            ["lane_id"],
            ["lanes.id"],
            name=op.f("fk_signal_states_lane_id_lanes"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signal_states")),
    )
    op.create_index(op.f("ix_signal_states_created_at"), "signal_states", ["created_at"])
    op.create_index(
        "ix_signal_states_intersection_id",
        "signal_states",
        ["intersection_id"],
    )
    op.create_index("ix_signal_states_started_at", "signal_states", ["started_at"])

    op.create_table(
        "traffic_readings",
        sa.Column("intersection_id", sa.Uuid(), nullable=False),
        sa.Column("lane_id", sa.Uuid(), nullable=True),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("vehicle_count", sa.Integer(), nullable=False),
        sa.Column(
            "density",
            sa.Enum(
                "low",
                "medium",
                "high",
                name="traffic_density",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_traffic_readings_device_id_devices"),
        ),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            name=op.f("fk_traffic_readings_intersection_id_intersections"),
        ),
        sa.ForeignKeyConstraint(
            ["lane_id"],
            ["lanes.id"],
            name=op.f("fk_traffic_readings_lane_id_lanes"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_traffic_readings")),
    )
    op.create_index(
        "ix_traffic_readings_captured_at",
        "traffic_readings",
        ["captured_at"],
    )
    op.create_index(op.f("ix_traffic_readings_created_at"), "traffic_readings", ["created_at"])
    op.create_index(
        "ix_traffic_readings_intersection_id",
        "traffic_readings",
        ["intersection_id"],
    )

    op.create_table(
        "violations",
        sa.Column("intersection_id", sa.Uuid(), nullable=False),
        sa.Column("lane_id", sa.Uuid(), nullable=True),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("violation_type", sa.String(length=80), nullable=False),
        sa.Column("evidence_uri", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_violations_device_id_devices"),
        ),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            name=op.f("fk_violations_intersection_id_intersections"),
        ),
        sa.ForeignKeyConstraint(
            ["lane_id"],
            ["lanes.id"],
            name=op.f("fk_violations_lane_id_lanes"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_violations")),
    )
    op.create_index(op.f("ix_violations_created_at"), "violations", ["created_at"])
    op.create_index("ix_violations_intersection_id", "violations", ["intersection_id"])
    op.create_index("ix_violations_occurred_at", "violations", ["occurred_at"])

    op.create_table(
        "incidents",
        sa.Column("intersection_id", sa.Uuid(), nullable=False),
        sa.Column("lane_id", sa.Uuid(), nullable=True),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "investigating",
                "resolved",
                name="incident_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_incidents_device_id_devices"),
        ),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            name=op.f("fk_incidents_intersection_id_intersections"),
        ),
        sa.ForeignKeyConstraint(
            ["lane_id"],
            ["lanes.id"],
            name=op.f("fk_incidents_lane_id_lanes"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
    )
    op.create_index(op.f("ix_incidents_created_at"), "incidents", ["created_at"])
    op.create_index("ix_incidents_intersection_id", "incidents", ["intersection_id"])
    op.create_index("ix_incidents_reported_at", "incidents", ["reported_at"])
    op.create_index("ix_incidents_status", "incidents", ["status"])

    op.create_table(
        "alerts",
        sa.Column("intersection_id", sa.Uuid(), nullable=False),
        sa.Column("lane_id", sa.Uuid(), nullable=True),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("incident_id", sa.Uuid(), nullable=True),
        sa.Column("acknowledged_by_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "severity",
            sa.Enum(
                "info",
                "warning",
                "critical",
                name="alert_severity",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "acknowledged",
                "resolved",
                name="alert_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["acknowledged_by_id"],
            ["users.id"],
            name=op.f("fk_alerts_acknowledged_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_alerts_device_id_devices"),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_alerts_incident_id_incidents"),
        ),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            name=op.f("fk_alerts_intersection_id_intersections"),
        ),
        sa.ForeignKeyConstraint(
            ["lane_id"],
            ["lanes.id"],
            name=op.f("fk_alerts_lane_id_lanes"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index(op.f("ix_alerts_created_at"), "alerts", ["created_at"])
    op.create_index("ix_alerts_intersection_id", "alerts", ["intersection_id"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.drop_index("ix_alerts_severity", table_name="alerts")
    op.drop_index("ix_alerts_intersection_id", table_name="alerts")
    op.drop_index(op.f("ix_alerts_created_at"), table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_reported_at", table_name="incidents")
    op.drop_index("ix_incidents_intersection_id", table_name="incidents")
    op.drop_index(op.f("ix_incidents_created_at"), table_name="incidents")
    op.drop_table("incidents")
    op.drop_index("ix_violations_occurred_at", table_name="violations")
    op.drop_index("ix_violations_intersection_id", table_name="violations")
    op.drop_index(op.f("ix_violations_created_at"), table_name="violations")
    op.drop_table("violations")
    op.drop_index("ix_traffic_readings_intersection_id", table_name="traffic_readings")
    op.drop_index(op.f("ix_traffic_readings_created_at"), table_name="traffic_readings")
    op.drop_index("ix_traffic_readings_captured_at", table_name="traffic_readings")
    op.drop_table("traffic_readings")
    op.drop_index("ix_signal_states_started_at", table_name="signal_states")
    op.drop_index("ix_signal_states_intersection_id", table_name="signal_states")
    op.drop_index(op.f("ix_signal_states_created_at"), table_name="signal_states")
    op.drop_table("signal_states")
    op.drop_index("ix_devices_status", table_name="devices")
    op.drop_index("ix_devices_intersection_id", table_name="devices")
    op.drop_index(op.f("ix_devices_created_at"), table_name="devices")
    op.drop_table("devices")
    op.drop_index("ix_lanes_intersection_id", table_name="lanes")
    op.drop_index(op.f("ix_lanes_created_at"), table_name="lanes")
    op.drop_table("lanes")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_created_at"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_intersections_created_at"), table_name="intersections")
    op.drop_table("intersections")
