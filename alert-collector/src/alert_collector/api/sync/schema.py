"""Schemas for sync endpoint."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SyncedAlertResponse(BaseModel):
    """Alert representation returned directly from sync result."""

    external_id: str
    created_at: datetime
    severity: str
    alert_type: str
    message: str | None
    enrichment_ip: str
    enrichment_type: str


class SyncResponse(BaseModel):
    """Response payload for manual sync trigger endpoint."""

    sync_run_id: UUID
    attempt_number: int
    retry_count: int
    since: datetime
    up_to: datetime
    checkpoint_updated: bool
    alerts: list[SyncedAlertResponse]
