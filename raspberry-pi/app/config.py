from __future__ import annotations

import uuid

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    device_id: uuid.UUID
    intersection_id: uuid.UUID
    software_version: str = "0.1.0"
    environment: str = "development"
    mqtt_enabled: bool = False
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_tls_enabled: bool = False
    mqtt_client_id: str = "itms-raspberry-pi"
    mqtt_keepalive_seconds: int = 60
    heartbeat_interval_seconds: float = Field(default=30, gt=0)
    telemetry_interval_seconds: float = Field(default=30, gt=0)
    command_max_age_seconds: int = Field(default=300, gt=0)
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()
