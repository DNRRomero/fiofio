"""Celery worker package."""

from alert_collector.worker.celery_app import celery_app
from alert_collector.worker.tasks import sync_alerts_task

__all__ = ["celery_app", "sync_alerts_task"]
