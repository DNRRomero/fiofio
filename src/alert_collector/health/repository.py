"""Health repository for ingestion and database probe data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID

from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session, sessionmaker

from alert_collector.db.models import WorkerExecution
from alert_collector.db.session import get_session_factory


@dataclass(frozen=True, slots=True)
class DatabaseProbe:
    """Database connectivity probe output."""

    status: str
    latency_ms: float | None
    error: str | None


@dataclass(frozen=True, slots=True)
class WorkerExecutionRecord:
    """Worker execution data used for health aggregation."""

    sync_run_id: UUID
    attempt_number: int
    success: bool
    started_at: datetime
    finished_at: datetime
    error_type: str | None
    error_message: str | None


class HealthRepository:
    """Read-only persistence access for health computations."""

    def __init__(self, *, session_factory: sessionmaker[Session] | None = None) -> None:
        self._session_factory = session_factory or get_session_factory()

    def probe_database(self) -> DatabaseProbe:
        """Return DB up/down status and query latency."""
        started = perf_counter()
        try:
            with self._session_factory() as session:
                session.execute(text("SELECT 1"))
            latency_ms = (perf_counter() - started) * 1000.0
            return DatabaseProbe(status="up", latency_ms=round(latency_ms, 3), error=None)
        except Exception as exc:
            return DatabaseProbe(status="down", latency_ms=None, error=str(exc))

    def list_recent_executions(self, *, lookback_hours: int = 12) -> list[WorkerExecutionRecord]:
        """Fetch recent worker executions for health-window evaluation."""
        threshold = datetime.now(tz=UTC) - timedelta(hours=lookback_hours)
        stmt: Select[tuple[WorkerExecution]] = (
            select(WorkerExecution)
            .where(WorkerExecution.finished_at >= threshold)
            .order_by(WorkerExecution.finished_at.desc(), WorkerExecution.attempt_number.desc())
        )
        with self._session_factory() as session:
            rows = session.execute(stmt).scalars().all()

        return [
            WorkerExecutionRecord(
                sync_run_id=row.sync_run_id,
                attempt_number=row.attempt_number,
                success=row.success,
                started_at=row.started_at,
                finished_at=row.finished_at,
                error_type=row.error_type,
                error_message=row.error_message,
            )
            for row in rows
        ]

