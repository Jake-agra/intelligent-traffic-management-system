from functools import lru_cache
import uuid

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "Intelligent Traffic Management System API"
    api_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/traffic_management"
    )
    backend_cors_origins: str = "http://localhost:3000,http://localhost:5173"
    jwt_secret_key: str = "change-this-secret-before-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    max_signal_override_seconds: int = 180
    mqtt_enabled: bool = False
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_tls_enabled: bool = False
    mqtt_client_id: str = "itms-backend"
    mqtt_keepalive_seconds: int = 60
    mqtt_max_telemetry_age_seconds: int = 300
    hardware_test_intersection_id: uuid.UUID | None = None
    hardware_test_north_lane_id: uuid.UUID | None = None
    hardware_test_south_lane_id: uuid.UUID | None = None
    hardware_test_east_lane_id: uuid.UUID | None = None
    hardware_test_west_lane_id: uuid.UUID | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("backend_cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("At least one CORS origin must be configured.")
        return ",".join(origins)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
