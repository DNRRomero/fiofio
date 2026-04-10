"""Alert enrichment logic."""

from datetime import datetime
from ipaddress import IPv4Address
from random import randint
from typing import Any

from pydantic import BaseModel

from alert_collector.external_client.schemas import ExternalAlert


class EnrichedAlert(BaseModel):
    """External alert enriched with collector-derived fields."""

    external_id: str
    created_at: datetime
    severity: str
    alert_type: str
    message: str | None
    raw_payload: dict[str, Any]
    enrichment_ip: str
    enrichment_type: str


def random_ipv4() -> str:
    """Return a random IPv4 address in dotted-decimal format."""
    return str(IPv4Address(randint(0, 2**32 - 1)))


def enrich_alert(alert: ExternalAlert) -> EnrichedAlert:
    """Enrich a single external alert with pseudo-random metadata."""
    return EnrichedAlert(
        external_id=alert.external_id,
        created_at=alert.created_at,
        severity=alert.severity,
        alert_type=alert.alert_type,
        message=alert.message,
        raw_payload=alert.raw_payload,
        enrichment_ip=random_ipv4(),
        enrichment_type="random_ipv4",
    )
