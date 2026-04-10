"""Application configuration loaded from environment."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _BaseSliceSettings(BaseSettings):
    """Shared pydantic-settings configuration for all slices."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


class DatabaseSettings(_BaseSliceSettings):
    """Database-related settings."""

    database_url: str = Field(alias="DATABASE_URL")


class WorkerSettings(_BaseSliceSettings):
    """Celery worker and beat settings."""

    rabbit_mq: str = Field(alias="RABBIT_MQ")
    sync_frequency_minutes: int = Field(default=15, alias="SYNC_FREQUENCY_MINUTES")


class ExternalClientSettings(_BaseSliceSettings):
    """External alerts service integration settings."""

    external_service_host: str = Field(alias="EXTERNAL_SERVICE_HOST")
    external_service_token: str = Field(alias="EXTERNAL_SERVICE_TOKEN")


class ApiSettings(_BaseSliceSettings):
    """FastAPI-facing settings."""

    service_host: str = Field(default="http://localhost:8000", alias="SERVICE_HOST")
    cursor_hmac_secret: str = Field(
        default="dev-cursor-secret", alias="CURSOR_HMAC_SECRET"
    )


class SyncSettings(_BaseSliceSettings):
    """Sync orchestration settings."""

    sync_bootstrap_lookback_minutes: int = Field(
        default=15, alias="SYNC_BOOTSTRAP_LOOKBACK_MINUTES"
    )


class HealthSettings(_BaseSliceSettings):
    """Health evaluation threshold settings."""

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


@lru_cache
def get_worker_settings() -> WorkerSettings:
    """Return cached worker settings."""
    return WorkerSettings()


@lru_cache
def get_external_client_settings() -> ExternalClientSettings:
    """Return cached external-client settings."""
    return ExternalClientSettings()


@lru_cache
def get_sync_settings() -> SyncSettings:
    """Return cached sync settings."""
    return SyncSettings()


@lru_cache
def get_health_settings() -> HealthSettings:
    """Return cached health settings."""
    return HealthSettings()
