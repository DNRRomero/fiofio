"""External service integration package."""

from alert_collector.external_client.client import (
    ExternalAlertsClient,
    ExternalClientError,
    ExternalClientServerError,
)
from alert_collector.external_client.schemas import ExternalAlert

__all__ = [
    "ExternalAlert",
    "ExternalAlertsClient",
    "ExternalClientError",
    "ExternalClientServerError",
]
