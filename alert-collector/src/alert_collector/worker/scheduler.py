"""Celery beat scheduling helpers."""

from celery.schedules import crontab

from alert_collector.settings import WorkerSettings


def build_beat_schedule(
    settings: WorkerSettings,
) -> dict[str, dict[str, object]]:
    """Build the periodic task schedule for sync ingestion."""
    worker_settings = settings
    frequency = max(worker_settings.sync_frequency_minutes, 1)
    return {
        "alerts-sync-periodic": {
            "task": "alert_collector.sync_alerts",
            "schedule": crontab(minute=f"*/{frequency}"),
        }
    }
