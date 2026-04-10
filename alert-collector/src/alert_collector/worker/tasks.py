"""Celery task definitions."""

from uuid import UUID, uuid4

from alert_collector.sync import (
    SyncExternalFailureError,
    SyncLockUnavailableError,
    SyncService,
)


def sync_alerts_task(self, *, sync_run_id: str | None = None) -> dict[str, object]:  # noqa: ANN001
    """Run one sync attempt and retry on transient ingestion failures."""
    run_id = UUID(sync_run_id) if sync_run_id else uuid4()
    attempt_number = self.request.retries + 1

    service = SyncService()
    try:
        result = service.sync_alerts(
            sync_run_id=run_id,
            attempt_number=attempt_number,
            retry_count=max(attempt_number - 1, 0),
        )
    except (SyncExternalFailureError, SyncLockUnavailableError) as exc:
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
