from datetime import datetime

from fastapi_pagination.cursor import CursorParams
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import Select, select

from alert_collector.api.alerts.schema import AlertResponse, AlertsCursorPage
from alert_collector.db.models import Alert
from alert_collector.db.session import get_session
from alert_collector.settings import ApiSettings


def _as_alert_response(model: Alert) -> AlertResponse:
    return AlertResponse(
        id=model.id,
        external_id=model.external_id,
        created_at=model.created_at,
        severity=model.severity,
        alert_type=model.alert_type,
        message=model.message,
        enrichment_ip=model.enrichment_ip,
        enrichment_type=model.enrichment_type,
        ingested_at=model.ingested_at,
    )


class AlertsService:
    def __init__(self, settings: ApiSettings):
        self._settings = settings

    def _build_stmt(
        self,
        since: datetime | None,
        up_to: datetime | None,
        severity: str | None,
    ) -> Select[tuple[Alert]]:
        stmt: Select[tuple[Alert]] = select(Alert)
        if since is not None:
            stmt = stmt.where(Alert.created_at >= since)
        if up_to is not None:
            stmt = stmt.where(Alert.created_at <= up_to)
        if severity is not None:
            stmt = stmt.where(Alert.severity == severity)
        return stmt.order_by(Alert.created_at.desc(), Alert.id.desc())

    def list_alerts(
        self,
        since: datetime | None,
        up_to: datetime | None,
        severity: str | None,
        params: CursorParams,
    ) -> AlertsCursorPage:
        """Return alerts ordered by created_at DESC, id DESC with cursor pagination."""
        stmt = self._build_stmt(since, up_to, severity)
        with get_session() as session:
            return paginate(
                session,
                stmt,
                params=params,
                transformer=lambda items: [_as_alert_response(item) for item in items],
            )
