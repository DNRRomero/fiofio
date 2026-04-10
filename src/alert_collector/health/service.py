"""Health status service with deterministic threshold evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import UUID

from alert_collector.health.repository import DatabaseProbe, HealthRepository, WorkerExecutionRecord
from alert_collector.settings import HealthSettings, get_health_settings


@dataclass(frozen=True, slots=True)
class IngestionError:
    """Recent ingestion error output."""

    sync_run_id: UUID
    attempt_number: int
    error_type: str | None
    error_message: str | None
    finished_at: datetime


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Structured service health output."""

    status: str
    database: DatabaseProbe
    last_successful_sync: datetime | None
    error_rate_last_hour: float
    p95_external_latency_seconds_last_hour: float
    recent_errors: list[IngestionError]


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, ceil(len(ordered) * 0.95) - 1))
    return ordered[index]


class HealthService:
    """Derive collector health from DB and worker execution history."""

    def __init__(
        self,
        *,
        repository: HealthRepository | None = None,
        settings: HealthSettings | None = None,
    ) -> None:
        self._repository = repository or HealthRepository()
        self._settings = settings or get_health_settings()

    def evaluate(self) -> HealthReport:
        """Return overall health with ingestion diagnostics."""
        database_probe = self._repository.probe_database()
        executions = self._repository.list_recent_executions(lookback_hours=12)
        deduped = self._dedupe_by_sync_run(executions)
        now = datetime.now(tz=UTC)

        one_hour_ago = now - timedelta(hours=1)
        last_hour = [item for item in deduped if item.finished_at >= one_hour_ago]

        total_last_hour = len(last_hour)
        errors_last_hour = sum(1 for item in last_hour if not item.success)
        error_rate = (errors_last_hour / total_last_hour) if total_last_hour else 0.0

        latencies = [
            (item.finished_at - item.started_at).total_seconds()
            for item in last_hour
            if item.success and item.finished_at >= item.started_at
        ]
        p95_latency = _p95(latencies)

        last_success = max((item.finished_at for item in deduped if item.success), default=None)
        stale_threshold = now - timedelta(minutes=self._settings.health_success_stale_minutes)
        has_success_in_12h = last_success is not None
        success_stale = has_success_in_12h and last_success < stale_threshold

        status = "ok"
        if database_probe.status != "up":
            status = "down"
        elif not has_success_in_12h:
            status = "down"
        elif error_rate >= self._settings.health_error_rate_down:
            status = "down"
        elif p95_latency >= self._settings.health_p95_down_seconds:
            status = "down"
        elif success_stale:
            status = "degraded"
        elif error_rate >= self._settings.health_error_rate_warn:
            status = "degraded"
        elif p95_latency >= self._settings.health_p95_warn_seconds:
            status = "degraded"

        recent_errors = [
            IngestionError(
                sync_run_id=item.sync_run_id,
                attempt_number=item.attempt_number,
                error_type=item.error_type,
                error_message=item.error_message,
                finished_at=item.finished_at,
            )
            for item in deduped
            if not item.success
        ][:10]

        return HealthReport(
            status=status,
            database=database_probe,
            last_successful_sync=last_success,
            error_rate_last_hour=round(error_rate, 4),
            p95_external_latency_seconds_last_hour=round(p95_latency, 4),
            recent_errors=recent_errors,
        )

    @staticmethod
    def _dedupe_by_sync_run(executions: list[WorkerExecutionRecord]) -> list[WorkerExecutionRecord]:
        latest_by_run: dict[UUID, WorkerExecutionRecord] = {}
        for item in executions:
            current = latest_by_run.get(item.sync_run_id)
            if current is None:
                latest_by_run[item.sync_run_id] = item
                continue
            if item.attempt_number > current.attempt_number:
                latest_by_run[item.sync_run_id] = item
                continue
            if item.attempt_number == current.attempt_number and item.finished_at > current.finished_at:
                latest_by_run[item.sync_run_id] = item
        return sorted(latest_by_run.values(), key=lambda item: item.finished_at, reverse=True)

