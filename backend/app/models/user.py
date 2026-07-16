from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import UserRole, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


if TYPE_CHECKING:
    from app.models.auth import RefreshToken
    from app.models.history import AuditLog, SignalEvent
    from app.models.traffic import Alert


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=UserRole.ANALYST,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    acknowledged_alerts: Mapped[list["Alert"]] = relationship(
        back_populates="acknowledged_by",
    )
    signal_events: Mapped[list["SignalEvent"]] = relationship(
        back_populates="responsible_user",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        foreign_keys="RefreshToken.user_id",
    )
