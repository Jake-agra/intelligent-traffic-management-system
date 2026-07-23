"""add controller state

Revision ID: 0004_add_controller_state
Revises: 0003_add_authentication_foundation
Create Date: 2026-07-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_add_controller_state"
down_revision: Union[str, None] = "0003_add_authentication_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "controller_states",
        sa.Column("intersection_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column(
            "mode",
            sa.Enum(
                "automatic",
                "manual",
                "failsafe",
                name="operating_mode",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "requested_mode",
            sa.Enum(
                "automatic",
                "manual",
                "failsafe",
                name="operating_mode",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("command_status", sa.String(length=40), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=True),
        sa.Column("phase", sa.String(length=80), nullable=True),
        sa.Column("phase_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("phase_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("next_phase", sa.String(length=80), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_controller_states_device_id_devices"),
        ),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            name=op.f("fk_controller_states_intersection_id_intersections"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_controller_states_updated_by_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_controller_states")),
        sa.UniqueConstraint(
            "intersection_id",
            name="uq_controller_states_intersection_id",
        ),
    )
    op.create_index(
        op.f("ix_controller_states_created_at"),
        "controller_states",
        ["created_at"],
    )
    op.create_index("ix_controller_states_device_id", "controller_states", ["device_id"])
    op.create_index(
        "ix_controller_states_intersection_id",
        "controller_states",
        ["intersection_id"],
    )
    op.create_index("ix_controller_states_mode", "controller_states", ["mode"])


def downgrade() -> None:
    op.drop_index("ix_controller_states_mode", table_name="controller_states")
    op.drop_index("ix_controller_states_intersection_id", table_name="controller_states")
    op.drop_index("ix_controller_states_device_id", table_name="controller_states")
    op.drop_index(op.f("ix_controller_states_created_at"), table_name="controller_states")
    op.drop_table("controller_states")
