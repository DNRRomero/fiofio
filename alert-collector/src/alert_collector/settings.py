"""Application configuration loaded from environment."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _BaseSliceSettings(BaseSettings):
    """Shared pydantic-settings configuration for all slices."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        secrets_dir="/run/secrets",
        extra="ignore",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


class DatabaseSettings(_BaseSliceSettings):
    """Database-related settings."""

    database_url: str = Field(alias="DATABASE_URL")


class ExternalClientSettings(_BaseSliceSettings):
    """External alerts service integration settings."""

    external_service_host: str = Field(alias="EXTERNAL_SERVICE_HOST")
    external_service_token: str = Field(alias="EXTERNAL_SERVICE_TOKEN")


class SyncSettings(_BaseSliceSettings):
    """Sync orchestration settings."""

    sync_frequency_minutes: int = Field(default=15, alias="SYNC_FREQUENCY_MINUTES")


class ApiSettings(ExternalClientSettings, SyncSettings):
    """FastAPI-facing settings."""


class WorkerSettings(ExternalClientSettings, SyncSettings):
    """Celery worker and beat settings."""

    rabbit_mq: str = Field(alias="RABBIT_MQ")
    rabbit_mq_tls_ca_cert: str = Field(
        default="/run/secrets/rabbitmq_ca_cert",
        validation_alias=AliasChoices("RABBIT_MQ_TLS_CA_CERT", "RABBIT_MQ_CA_CERT"),
    )
    max_retries: int = Field(default=3, alias="MAX_RETRIES")


class HealthSettings(_BaseSliceSettings):
    """Health evaluation threshold settings."""

    prometheus_url: str = Field(alias="PROMETHEUS_URL")
    health_recent_success_hours: int = Field(
        default=3, alias="HEALTH_RECENT_SUCCESS_HOURS"
    )
    health_success_stale_minutes: int = Field(
        default=30, alias="HEALTH_SUCCESS_STALE_MINUTES"
    )
    health_error_rate_warn: float = Field(default=0.20, alias="HEALTH_ERROR_RATE_WARN")
    health_error_rate_down: float = Field(default=0.50, alias="HEALTH_ERROR_RATE_DOWN")
    health_p95_warn_seconds: float = Field(default=2.0, alias="HEALTH_P95_WARN_SECONDS")
    health_p95_down_seconds: float = Field(default=5.0, alias="HEALTH_P95_DOWN_SECONDS")


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Return cached database settings."""
    return DatabaseSettings()
