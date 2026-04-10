"""Route for health endpoint."""

from fastapi import APIRouter, Depends

from alert_collector.api.health.schema import (
    DatabaseHealthResponse,
    HealthResponse,
    IngestionErrorResponse,
)
from alert_collector.auth import current_active_user
from alert_collector.db.models.user import User
from alert_collector.health import HealthService
from alert_collector.settings import HealthSettings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health(_user: User = Depends(current_active_user)) -> HealthResponse:
    """Return collector health status and diagnostics."""
    settings = HealthSettings()
    report = HealthService(settings=settings).evaluate()
    return HealthResponse(
        status=report.status,
        database=DatabaseHealthResponse(
            status=report.database.status,
            latency_ms=report.database.latency_ms,
            error=report.database.error,
        ),
        last_successful_sync=report.last_successful_sync,
        error_rate_last_hour=report.error_rate_last_hour,
        p95_external_latency_seconds_last_hour=report.p95_external_latency_seconds_last_hour,
        recent_errors=[
            IngestionErrorResponse(
                sync_run_id=item.sync_run_id,
                attempt_number=item.attempt_number,
                error_type=item.error_type,
                error_message=item.error_message,
                finished_at=item.finished_at,
            )
            for item in report.recent_errors
        ],
    )
