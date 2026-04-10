"""Celery beat scheduling helpers."""

from celery.schedules import crontab

from alert_collector.settings import WorkerSettings, get_worker_settings


def build_beat_schedule(
    settings: WorkerSettings | None = None,
) -> dict[str, dict[str, object]]:
    """Build the periodic task schedule for sync ingestion."""
    worker_settings = settings or get_worker_settings()
    frequency = max(worker_settings.sync_frequency_minutes, 1)
    return {
        "alerts-sync-periodic": {
            "task": "alert_collector.sync_alerts",
            "schedule": crontab(minute=f"*/{frequency}"),
        }
    }
