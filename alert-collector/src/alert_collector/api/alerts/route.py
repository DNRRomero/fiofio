"""Route for alerts endpoint."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi_pagination.cursor import CursorParams

from alert_collector.api.alerts.app import AlertsService
from alert_collector.api.alerts.schema import AlertsCursorPage
from alert_collector.auth import current_active_user
from alert_collector.db.models.user import User
from alert_collector.settings import ApiSettings

router = APIRouter(tags=["alerts"])


class AlertsCursorParams(CursorParams):
    size: Annotated[int, Query(default=50, ge=1, le=200)]


def get_alerts_service() -> AlertsService:
    settings = ApiSettings()
    return AlertsService(settings)


@router.get("/alerts", response_model=AlertsCursorPage)
def list_alerts(
    since: datetime | None = Query(default=None),
    up_to: datetime | None = Query(default=None),
    severity: str | None = Query(default=None),
    params: AlertsCursorParams = Depends(),
    service: AlertsService = Depends(get_alerts_service),
    _user: User = Depends(current_active_user),
):
    return service.list_alerts(since, up_to, severity, params)
