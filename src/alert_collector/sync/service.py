"""Shared sync orchestration service."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from alert_collector.db.models import ALERTS_SINCE_CHECKPOINT_KEY, Alert, KeyValueState, WorkerExecution
from alert_collector.db.session import get_session_factory
from alert_collector.enrichment.service import EnrichedAlert, enrich_alert
from alert_collector.external_client.client import ExternalAlertsClient, ExternalClientError
from alert_collector.metrics import track_external_alerts_call_duration
from alert_collector.settings import SyncSettings, get_sync_settings
from alert_collector.sync.locking import acquire_transaction_lock


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_checkpoint(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _serialize_checkpoint(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Result of a single sync attempt."""

    sync_run_id: UUID
    attempt_number: int
    retry_count: int
    since: datetime
    up_to: datetime
    alerts: list[EnrichedAlert]
    checkpoint_updated: bool


class SyncServiceError(Exception):
    """Base exception for sync orchestration failures."""


class SyncExternalFailureError(SyncServiceError):
    """Raised when external API ingestion fails."""


class SyncService:
    """Run alert synchronization with atomic persistence semantics."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        external_client: ExternalAlertsClient | None = None,
        settings: SyncSettings | None = None,
    ) -> None:
        self._session_factory = session_factory or get_session_factory()
        self._external_client = external_client or ExternalAlertsClient()
        self._settings = settings or get_sync_settings()

    def sync_alerts(
        self,
        *,
        sync_run_id: UUID | None = None,
        attempt_number: int | None = None,
        retry_count: int | None = None,
        lock_name: str = "alerts_sync",
    ) -> SyncResult:
        """Run one sync attempt and commit all related changes atomically."""
        run_id = sync_run_id or uuid4()
        started_at = _utc_now()
        pending_error: Exception | None = None
        result: SyncResult | None = None

        with self._session_factory() as session:
            with session.begin():
                acquire_transaction_lock(session, lock_name=lock_name)
                attempt = attempt_number or self._next_attempt_number(session, run_id)
                retries = retry_count if retry_count is not None else max(attempt - 1, 0)

                since = self._resolve_since_checkpoint(session, reference_time=started_at)
                up_to = _utc_now()

                try:
                    with track_external_alerts_call_duration():
                        external_alerts = self._external_client.get_alerts(since=since, up_to=up_to)
                    enriched_alerts = [enrich_alert(alert) for alert in external_alerts]
                    self._upsert_alerts(session, enriched_alerts)
                    checkpoint_updated = self._update_checkpoint_monotonic(session, up_to=up_to)

                    finished_at = _utc_now()
                    summary = {
                        "alerts_received": len(external_alerts),
                        "alerts_persisted": len(enriched_alerts),
                        "checkpoint": _serialize_checkpoint(up_to),
                        "checkpoint_updated": checkpoint_updated,
                    }
                    self._insert_execution(
                        session=session,
                        sync_run_id=run_id,
                        attempt_number=attempt,
                        retry_count=retries,
                        started_at=started_at,
                        finished_at=finished_at,
                        success=True,
                        summary=summary,
                    )
                    result = SyncResult(
                        sync_run_id=run_id,
                        attempt_number=attempt,
                        retry_count=retries,
                        since=since,
                        up_to=up_to,
                        alerts=enriched_alerts,
                        checkpoint_updated=checkpoint_updated,
                    )
                except (ExternalClientError, ValueError, RuntimeError) as exc:
                    finished_at = _utc_now()
                    self._insert_execution(
                        session=session,
                        sync_run_id=run_id,
                        attempt_number=attempt,
                        retry_count=retries,
                        started_at=started_at,
                        finished_at=finished_at,
                        success=False,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                    pending_error = exc

        if pending_error is not None:
            raise SyncExternalFailureError("sync failed while ingesting external alerts") from pending_error
        if result is None:
            raise SyncServiceError("sync completed without producing a result")
        return result

    def _resolve_since_checkpoint(self, session: Session, *, reference_time: datetime) -> datetime:
        checkpoint = session.get(KeyValueState, ALERTS_SINCE_CHECKPOINT_KEY)
        if checkpoint is None:
            lookback = timedelta(minutes=self._settings.sync_bootstrap_lookback_minutes)
            return (reference_time - lookback).astimezone(UTC)
        return _parse_checkpoint(checkpoint.value)

    def _next_attempt_number(self, session: Session, sync_run_id: UUID) -> int:
        stmt: Select[tuple[int | None]] = select(func.max(WorkerExecution.attempt_number)).where(
            WorkerExecution.sync_run_id == sync_run_id
        )
        current_max = session.execute(stmt).scalar_one_or_none()
        return 1 if current_max is None else current_max + 1

    def _update_checkpoint_monotonic(self, session: Session, *, up_to: datetime) -> bool:
        checkpoint = session.get(KeyValueState, ALERTS_SINCE_CHECKPOINT_KEY)
        if checkpoint is None:
            session.add(KeyValueState(key=ALERTS_SINCE_CHECKPOINT_KEY, value=_serialize_checkpoint(up_to)))
            return True

        current_value = _parse_checkpoint(checkpoint.value)
        if up_to <= current_value:
            return False

        checkpoint.value = _serialize_checkpoint(up_to)
        return True

    def _upsert_alerts(self, session: Session, alerts: list[EnrichedAlert]) -> None:
        if not alerts:
            return

        values: list[dict[str, Any]] = [asdict(alert) for alert in alerts]
        stmt = pg_insert(Alert).values(values)
        excluded = stmt.excluded
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[Alert.external_id],
            set_={
                "created_at": excluded.created_at,
                "severity": excluded.severity,
                "alert_type": excluded.alert_type,
                "message": excluded.message,
                "enrichment_ip": excluded.enrichment_ip,
                "enrichment_type": excluded.enrichment_type,
                "raw_payload": excluded.raw_payload,
            },
        )
        session.execute(upsert_stmt)

    def _insert_execution(
        self,
        *,
        session: Session,
        sync_run_id: UUID,
        attempt_number: int,
        retry_count: int,
        started_at: datetime,
        finished_at: datetime,
        success: bool,
        summary: dict[str, Any] | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        session.add(
            WorkerExecution(
                sync_run_id=sync_run_id,
                attempt_number=attempt_number,
                retry_count=retry_count,
                success=success,
                started_at=started_at,
                finished_at=finished_at,
                summary=summary,
                error_type=error_type,
                error_message=error_message,
            )
        )

