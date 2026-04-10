"""Schemas for health endpoint."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DatabaseHealthResponse(BaseModel):
    """Database health probe details."""

    status: str
    latency_ms: float | None
    error: str | None


class IngestionErrorResponse(BaseModel):
    """Recent ingestion error details."""

    sync_run_id: UUID
    attempt_number: int
    error_type: str | None
    error_message: str | None
    finished_at: datetime


class HealthResponse(BaseModel):
    """Service health endpoint response."""

    status: str
    database: DatabaseHealthResponse
    last_successful_sync: datetime | None
    error_rate_last_hour: float
    p95_external_latency_seconds_last_hour: float
    recent_errors: list[IngestionErrorResponse]
