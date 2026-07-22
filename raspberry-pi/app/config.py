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
    gpio_enabled: bool = False
    traffic_light_north_red_pin: int = Field(default=22, ge=0)
    traffic_light_north_yellow_pin: int = Field(default=27, ge=0)
    traffic_light_north_green_pin: int = Field(default=17, ge=0)
    traffic_light_south_red_pin: int = Field(default=5, ge=0)
    traffic_light_south_yellow_pin: int = Field(default=6, ge=0)
    traffic_light_south_green_pin: int = Field(default=13, ge=0)
    traffic_light_east_red_pin: int = Field(default=19, ge=0)
    traffic_light_east_yellow_pin: int = Field(default=26, ge=0)
    traffic_light_east_green_pin: int = Field(default=21, ge=0)
    traffic_light_west_red_pin: int = Field(default=16, ge=0)
    traffic_light_west_yellow_pin: int = Field(default=20, ge=0)
    traffic_light_west_green_pin: int = Field(default=12, ge=0)
    traffic_light_green_pin: int = Field(default=17, ge=0)
    traffic_light_yellow_pin: int = Field(default=27, ge=0)
    traffic_light_red_pin: int = Field(default=22, ge=0)
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
