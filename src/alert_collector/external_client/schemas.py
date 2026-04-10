"""Schemas for external alerts payloads."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class ExternalAlert(BaseModel):
    """Alert schema from the external API."""

    class Severity(StrEnum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"

    id: UUID
    source: str
    severity: Severity
    description: str
    created_at: datetime
