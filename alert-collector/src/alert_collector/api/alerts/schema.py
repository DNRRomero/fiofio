"""Schemas for alerts endpoint."""

from datetime import datetime

from fastapi_pagination.cursor import CursorPage
from fastapi_pagination.customization import (
    CustomizedPage,
    UseExcludedFields,
    UseFieldsAliases,
)
from pydantic import BaseModel


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


AlertsCursorPage = CustomizedPage[
    CursorPage[AlertResponse],
    UseFieldsAliases(items="alerts"),
    UseExcludedFields("current_page", "current_page_backwards"),
]
