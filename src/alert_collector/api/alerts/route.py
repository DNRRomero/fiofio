"""Route for alerts endpoint."""

from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import Select, and_, or_, select

from alert_collector.api.alerts.schema import AlertResponse, AlertsPageResponse
from alert_collector.api.pagination import (
    CursorPayload,
    assert_cursor_continuity,
    decode_cursor,
    encode_cursor,
    register_cursor_snapshot,
    snapshot_from_filters,
)
from alert_collector.db.models import Alert
from alert_collector.db.session import get_session
from alert_collector.settings import get_api_settings

router = APIRouter(tags=["alerts"])


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


def _build_page_link(*, cursor: str | None, since: datetime | None, up_to: datetime | None, severity: str | None, limit: int) -> str | None:
    if cursor is None:
        return None

    params: dict[str, str] = {"cursor": cursor, "limit": str(limit)}
    if since is not None:
        params["since"] = since.isoformat()
    if up_to is not None:
        params["up_to"] = up_to.isoformat()
    if severity is not None:
        params["severity"] = severity

    settings = get_api_settings()
    return f"{settings.service_host.rstrip('/')}/alerts?{urlencode(params)}"


@router.get("/alerts", response_model=AlertsPageResponse)
def list_alerts(
    since: datetime | None = Query(default=None),
    up_to: datetime | None = Query(default=None),
    severity: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> AlertsPageResponse:
    """Return alerts ordered by created_at DESC, id DESC with cursor pagination."""
    snapshot = snapshot_from_filters(since=since, up_to=up_to, severity=severity)
    cursor_payload: CursorPayload | None = None
    if cursor is not None:
        try:
            cursor_payload = decode_cursor(cursor)
            assert_cursor_continuity(token=cursor, current_snapshot=snapshot)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    stmt: Select[tuple[Alert]] = select(Alert)
    if since is not None:
        stmt = stmt.where(Alert.created_at >= since)
    if up_to is not None:
        stmt = stmt.where(Alert.created_at <= up_to)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if cursor_payload is not None:
        stmt = stmt.where(
            or_(
                Alert.created_at < cursor_payload.created_at,
                and_(
                    Alert.created_at == cursor_payload.created_at,
                    Alert.id < cursor_payload.alert_id,
                ),
            )
        )

    stmt = stmt.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit + 1)
    with get_session() as session:
        rows = session.execute(stmt).scalars().all()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor: str | None = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = encode_cursor(
            CursorPayload(created_at=last.created_at, alert_id=last.id, direction="next")
        )
        register_cursor_snapshot(token=next_cursor, snapshot=snapshot)

    return AlertsPageResponse(
        alerts=[_as_alert_response(item) for item in page_rows],
        next_cursor=next_cursor,
        previous_cursor=None,
        next=_build_page_link(
            cursor=next_cursor,
            since=since,
            up_to=up_to,
            severity=severity,
            limit=limit,
        ),
        previous=None,
    )
