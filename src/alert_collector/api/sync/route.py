"""Route for sync endpoint."""

from fastapi import APIRouter, HTTPException, status

from alert_collector.api.sync.schema import SyncResponse, SyncedAlertResponse
from alert_collector.sync import SyncExternalFailureError, SyncLockUnavailableError, SyncService

router = APIRouter(tags=["sync"])


@router.post("/sync", response_model=SyncResponse, status_code=status.HTTP_201_CREATED)
def trigger_sync() -> SyncResponse:
    """Run the same sync action used by worker tasks."""
    service = SyncService()
    try:
        result = service.sync_alerts()
    except SyncExternalFailureError as exc:
        raise HTTPException(status_code=502, detail="failed to fetch external alerts") from exc
    except SyncLockUnavailableError as exc:
        raise HTTPException(status_code=409, detail="sync already in progress") from exc

    alerts = [
        SyncedAlertResponse(
            external_id=item.external_id,
            created_at=item.created_at,
            severity=item.severity,
            alert_type=item.alert_type,
            message=item.message,
            enrichment_ip=item.enrichment_ip,
            enrichment_type=item.enrichment_type,
        )
        for item in result.alerts
    ]

    return SyncResponse(
        sync_run_id=result.sync_run_id,
        attempt_number=result.attempt_number,
        retry_count=result.retry_count,
        since=result.since,
        up_to=result.up_to,
        checkpoint_updated=result.checkpoint_updated,
        alerts=alerts,
    )
