"""Celery application wiring."""

from celery import Celery

from alert_collector.settings import get_worker_settings
from alert_collector.worker.scheduler import build_beat_schedule

settings = get_worker_settings()

celery_app = Celery("alert_collector", broker=settings.rabbit_mq)
celery_app.conf.update(
    broker_url=settings.rabbit_mq,
    task_default_queue="alert-collector",
    timezone="UTC",
    enable_utc=True,
    beat_schedule=build_beat_schedule(settings),
    imports=("alert_collector.worker.tasks",),
)
