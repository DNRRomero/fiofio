"""External alerts HTTP client integration."""

from datetime import datetime

import httpx
from pydantic import ValidationError

from alert_collector.external_client.schemas import ExternalAlert
from alert_collector.metrics import track_external_alerts_call_duration


class ExternalClientError(Exception):
    """Raised when the external API request fails or payload is invalid."""


class ExternalClientServerError(ExternalClientError):
    """Raised when the external API returns a 5xx status code."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"external API returned server error {status_code}")
        self.status_code = status_code


class ExternalAlertsClient:
    """HTTP client for external alert ingestion API."""

    def __init__(
        self,
        external_client_host: str,
        external_client_token: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.external_client_host = external_client_host
        self.external_client_token = external_client_token
        self.timeout_seconds = timeout_seconds

    def get_alerts(self, *, since: datetime, up_to: datetime) -> list[ExternalAlert]:
        """Fetch alerts from the configured external service."""
        url = f"{self.external_client_host.rstrip('/')}/alerts/"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Token {self.external_client_token}",
        }
        params = {"since": since.isoformat(), "up_to": up_to.isoformat()}

        with track_external_alerts_call_duration():
            try:
                response = httpx.get(
                    url, params=params, headers=headers, timeout=self.timeout_seconds
                )
            except httpx.HTTPError as exc:
                raise ExternalClientError("external API request failed") from exc

            if response.status_code >= 500:
                raise ExternalClientServerError(response.status_code)
            if response.status_code != 200:
                raise ExternalClientError(
                    f"external API returned unexpected status {response.status_code}: {response.text}"
                )

            try:
                payload = response.json()
                raw_alerts = payload.get("alerts", [])
                return [ExternalAlert(**item) for item in raw_alerts]
            except ValidationError as exc:
                raise ExternalClientError(
                    "external API returned invalid alerts payload"
                ) from exc
            except Exception as exc:
                raise ExternalClientError("external API returned invalid JSON") from exc
