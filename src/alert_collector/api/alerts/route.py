"""Route for alerts endpoint."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from alert_collector.api.alerts.app import AlertsService
from alert_collector.api.alerts.schema import AlertsPageResponse

from alert_collector.settings import ApiSettings

router = APIRouter(tags=["alerts"])


def get_alerts_service() -> AlertsService:
    settings = ApiSettings()
    return AlertsService(settings.service_host, settings.cursor_hmac_secret)


@router.get("/alerts", response_model=AlertsPageResponse)
def list_alerts(
    since: datetime | None = Query(default=None),
    up_to: datetime | None = Query(default=None),
    severity: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    service: AlertsService = Depends(get_alerts_service),
):
    return service.list_alerts(since, up_to, severity, cursor, limit)
