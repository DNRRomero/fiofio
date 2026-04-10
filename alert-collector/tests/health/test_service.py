from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from alert_collector.health.prometheus import PrometheusHealthClient
from alert_collector.health.repository import DatabaseProbe, WorkerExecutionRecord
from alert_collector.health.service import HealthService
from alert_collector.settings import HealthSettings

PROMETHEUS_URL = "http://prometheus:9090"


class _StubHealthRepository:
    def __init__(
        self,
        *,
        probe: DatabaseProbe,
        executions: list[WorkerExecutionRecord],
    ) -> None:
        self._probe = probe
        self._executions = executions
        self.lookback_hours: int | None = None

    def probe_database(self) -> DatabaseProbe:
        return self._probe

    def list_recent_executions(
        self, *, lookback_hours: int = 12
    ) -> list[WorkerExecutionRecord]:
        self.lookback_hours = lookback_hours
        threshold = datetime.now(tz=UTC) - timedelta(hours=lookback_hours)
        return [
            execution
            for execution in self._executions
            if execution.finished_at >= threshold
        ]


class _StubPrometheusClient(PrometheusHealthClient):
    def __init__(
        self,
        *,
        external_latency_p95_last_hour: float = 0.0,
        external_latency_error: Exception | None = None,
    ) -> None:
        self._external_latency_p95_last_hour = external_latency_p95_last_hour
        self._external_latency_error = external_latency_error

    def get_external_latency_p95_last_hour(self) -> float:
        if self._external_latency_error is not None:
            raise self._external_latency_error
        return self._external_latency_p95_last_hour


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


def _settings() -> HealthSettings:
    return HealthSettings(
        PROMETHEUS_URL=PROMETHEUS_URL,
        HEALTH_RECENT_SUCCESS_HOURS=3,
        HEALTH_SUCCESS_STALE_MINUTES=30,
        HEALTH_ERROR_RATE_WARN=0.2,
        HEALTH_ERROR_RATE_DOWN=0.75,
        HEALTH_P95_WARN_SECONDS=2.0,
        HEALTH_P95_DOWN_SECONDS=5.0,
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
            1.2,
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
            1.5,
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
            1.5,
            "down",
        ),
        (
            DatabaseProbe(status="down", latency_ms=None, error="connection refused"),
            [],
            1.5,
            "down",
        ),
    ]
    for probe, executions, external_latency_p95_last_hour, expected_status in cases:
        service = HealthService(
            repository=_StubHealthRepository(probe=probe, executions=executions),
            prometheus_client=_StubPrometheusClient(
                external_latency_p95_last_hour=external_latency_p95_last_hour
            ),
            settings=_settings().model_copy(update={"health_error_rate_down": 0.5}),
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
    repository = _StubHealthRepository(
        probe=DatabaseProbe(status="up", latency_ms=3.2, error=None),
        executions=executions,
    )

    service = HealthService(
        repository=repository,
        settings=_settings(),
    )

    report = service.evaluate()

    assert repository.lookback_hours == 3
    assert report.error_rate_last_hour == 0.5
    assert len(report.recent_errors) == 1
    assert report.recent_errors[0].sync_run_id == failed_run_id


def test_health_is_down_without_success_in_last_three_hours() -> None:
    now = datetime.now(tz=UTC)
    repository = _StubHealthRepository(
        probe=DatabaseProbe(status="up", latency_ms=3.2, error=None),
        executions=[
            _execution(
                success=True,
                started_at=now - timedelta(hours=4, seconds=1),
                finished_at=now - timedelta(hours=4),
            )
        ],
    )
    service = HealthService(
        repository=repository,
        prometheus_client=_StubPrometheusClient(external_latency_p95_last_hour=1.0),
        settings=_settings(),
    )

    report = service.evaluate()

    assert report.status == "down"


def test_health_uses_prometheus_external_latency_thresholds() -> None:
    now = datetime.now(tz=UTC)
    service = HealthService(
        repository=_StubHealthRepository(
            probe=DatabaseProbe(status="up", latency_ms=3.2, error=None),
            executions=[
                _execution(
                    success=True,
                    started_at=now - timedelta(minutes=10, seconds=1),
                    finished_at=now - timedelta(minutes=10),
                )
            ],
        ),
        prometheus_client=_StubPrometheusClient(external_latency_p95_last_hour=5.5),
        settings=_settings(),
    )

    report = service.evaluate()

    assert report.status == "down"
    assert report.p95_external_latency_seconds_last_hour == 5.5


def test_health_degrades_when_prometheus_latency_is_unavailable() -> None:
    now = datetime.now(tz=UTC)
    service = HealthService(
        repository=_StubHealthRepository(
            probe=DatabaseProbe(status="up", latency_ms=3.2, error=None),
            executions=[
                _execution(
                    success=True,
                    started_at=now - timedelta(minutes=10, seconds=1),
                    finished_at=now - timedelta(minutes=10),
                )
            ],
        ),
        prometheus_client=_StubPrometheusClient(
            external_latency_error=RuntimeError("prometheus unavailable")
        ),
        settings=_settings(),
    )

    report = service.evaluate()

    assert report.status == "degraded"
    assert report.p95_external_latency_seconds_last_hour == 0.0
