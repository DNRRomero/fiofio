"""Schemas for alerts endpoint."""

from datetime import datetime

from pydantic import BaseModel, Field


class AlertResponse(BaseModel):
    """Alert representation returned by list endpoint."""

    id: int
    external_id: str
    created_at: datetime
    severity: str
    alert_type: str
    message: str | None
    enrichment_ip: str | None
    enrichment_type: str | None
    ingested_at: datetime


class AlertsPageResponse(BaseModel):
    """Cursor-paginated alerts response."""

    alerts: list[AlertResponse]
    next_cursor: str | None = Field(
        default=None, description="Opaque token for fetching the next page."
    )
    previous_cursor: str | None = Field(
        default=None, description="Opaque token for fetching the previous page."
    )
    next: str | None = Field(default=None, description="Absolute next-page URL.")
    previous: str | None = Field(
        default=None, description="Absolute previous-page URL."
    )
