"""Celery task definitions."""

from uuid import UUID, uuid4

from alert_collector.sync import (
    SyncExternalFailureError,
    SyncLockUnavailableError,
    initialize_sync_service,
)
from alert_collector.settings import WorkerSettings
import structlog

logger = structlog.get_logger()


def sync_alerts_task(self, *, sync_run_id: str | None = None) -> dict[str, object]:
    """Run one sync attempt and retry on transient ingestion failures."""
    logger.info("Starting sync attempt", sync_run_id=sync_run_id)
    run_id = UUID(sync_run_id) if sync_run_id else uuid4()
    attempt_number = self.request.retries + 1
    settings = WorkerSettings()
    service = initialize_sync_service(
        external_client_host=settings.external_service_host,
        external_client_token=settings.external_service_token,
        sync_frequency=settings.sync_frequency_minutes,
    )

    try:
        result = service.sync_alerts(
            sync_run_id=run_id,
            attempt_number=attempt_number,
            retry_count=max(attempt_number - 1, 0),
        )
        logger.info("Sync attempt completed", sync_run_id=run_id, result=result)
    except (SyncExternalFailureError, SyncLockUnavailableError) as exc:
        logger.error("Sync attempt failed", sync_run_id=run_id, error=exc)
        raise self.retry(
            exc=exc, kwargs={"sync_run_id": str(run_id)}, countdown=30
        ) from exc

    return {
        "sync_run_id": str(result.sync_run_id),
        "attempt_number": result.attempt_number,
        "retry_count": result.retry_count,
        "alerts_count": len(result.alerts),
        "since": result.since.isoformat(),
        "up_to": result.up_to.isoformat(),
        "checkpoint_updated": result.checkpoint_updated,
    }
