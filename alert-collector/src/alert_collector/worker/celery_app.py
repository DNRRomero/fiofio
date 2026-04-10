"""Celery application wiring."""

from celery import Celery

from alert_collector.settings import WorkerSettings
from alert_collector.worker.scheduler import build_beat_schedule
from alert_collector.worker.tasks import sync_alerts_task


def get_celery_app(settings: WorkerSettings) -> Celery:
    celery_app = Celery("alert_collector", broker=settings.rabbit_mq)
    celery_app.conf.update(
        broker_url=settings.rabbit_mq,
        task_default_queue="alert-collector",
        timezone="UTC",
        enable_utc=True,
        beat_schedule=build_beat_schedule(settings),
        imports=("alert_collector.worker.tasks",),
    )
    celery_app.task(
        bind=True, name="alert_collector.sync_alerts", max_retries=settings.max_retries
    )(sync_alerts_task)
    return celery_app
