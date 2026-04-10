from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from alert_collector.health.repository import DatabaseProbe, WorkerExecutionRecord
from alert_collector.health.service import HealthService
from alert_collector.settings import HealthSettings


class _StubHealthRepository:
    def __init__(
        self, *, probe: DatabaseProbe, executions: list[WorkerExecutionRecord]
    ) -> None:
        self._probe = probe
        self._executions = executions

    def probe_database(self) -> DatabaseProbe:
        return self._probe

    def list_recent_executions(
        self, *, lookback_hours: int = 12
    ) -> list[WorkerExecutionRecord]:
        del lookback_hours
        return self._executions


def _execution(
    *,
    success: bool,
    started_at: datetime,
    finished_at: datetime,
    run_id=None,
    attempt: int = 1,
) -> WorkerExecutionRecord:
    return WorkerExecutionRecord(
        sync_run_id=run_id or uuid4(),
        attempt_number=attempt,
        success=success,
        started_at=started_at,
        finished_at=finished_at,
        error_type=None if success else "RuntimeError",
        error_message=None if success else "failed",
    )


def test_health_status_thresholds() -> None:
    now = datetime.now(tz=UTC)
    cases = [
        (
            DatabaseProbe(status="up", latency_ms=4.1, error=None),
            [
                _execution(
                    success=True,
                    started_at=now - timedelta(minutes=5, seconds=1),
                    finished_at=now - timedelta(minutes=5),
                )
            ],
            "ok",
        ),
        (
            DatabaseProbe(status="up", latency_ms=5.0, error=None),
            [
                _execution(
                    success=True,
                    started_at=now - timedelta(minutes=40, seconds=1),
                    finished_at=now - timedelta(minutes=40),
                )
            ],
            "degraded",
        ),
        (
            DatabaseProbe(status="up", latency_ms=4.0, error=None),
            [
                _execution(
                    success=False,
                    started_at=now - timedelta(minutes=10, seconds=1),
                    finished_at=now - timedelta(minutes=10),
                ),
                _execution(
                    success=False,
                    started_at=now - timedelta(minutes=20, seconds=1),
                    finished_at=now - timedelta(minutes=20),
                ),
            ],
            "down",
        ),
        (
            DatabaseProbe(status="down", latency_ms=None, error="connection refused"),
            [],
            "down",
        ),
    ]
    for probe, executions, expected_status in cases:
        service = HealthService(
            repository=_StubHealthRepository(probe=probe, executions=executions),
            settings=HealthSettings(
                health_success_stale_minutes=30,
                health_error_rate_warn=0.2,
                health_error_rate_down=0.5,
                health_p95_warn_seconds=2.0,
                health_p95_down_seconds=5.0,
            ),
        )

        report = service.evaluate()

        assert report.status == expected_status


def test_health_dedupes_retries_by_sync_run() -> None:
    now = datetime.now(tz=UTC)
    recovered_run_id = uuid4()
    failed_run_id = uuid4()
    executions = [
        _execution(
            success=False,
            started_at=now - timedelta(minutes=26),
            finished_at=now - timedelta(minutes=25),
            run_id=recovered_run_id,
            attempt=1,
        ),
        _execution(
            success=True,
            started_at=now - timedelta(minutes=24),
            finished_at=now - timedelta(minutes=23),
            run_id=recovered_run_id,
            attempt=2,
        ),
        _execution(
            success=False,
            started_at=now - timedelta(minutes=8),
            finished_at=now - timedelta(minutes=7),
            run_id=failed_run_id,
            attempt=1,
        ),
    ]

    service = HealthService(
        repository=_StubHealthRepository(
            probe=DatabaseProbe(status="up", latency_ms=3.2, error=None),
            executions=executions,
        ),
        settings=HealthSettings(
            health_success_stale_minutes=30,
            health_error_rate_warn=0.2,
            health_error_rate_down=0.75,
            health_p95_warn_seconds=2.0,
            health_p95_down_seconds=5.0,
        ),
    )

    report = service.evaluate()

    assert report.error_rate_last_hour == 0.5
    assert len(report.recent_errors) == 1
    assert report.recent_errors[0].sync_run_id == failed_run_id
