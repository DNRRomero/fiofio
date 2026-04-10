"""Celery worker package."""

from alert_collector.worker.celery_app import get_celery_app
from alert_collector.worker.tasks import sync_alerts_task

__all__ = ["get_celery_app", "sync_alerts_task"]
