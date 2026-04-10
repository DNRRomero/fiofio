"""Celery application wiring."""

import ssl

from celery import Celery

from alert_collector.settings import WorkerSettings
from alert_collector.worker.scheduler import build_beat_schedule
from alert_collector.worker.tasks import sync_alerts_task


def _build_broker_tls_options(settings: WorkerSettings) -> dict[str, object] | None:
    """Enforce server certificate validation for amqps brokers."""
    if not settings.rabbit_mq.startswith("amqps://"):
        return None
    return {
        "ca_certs": settings.rabbit_mq_tls_ca_cert,
        "cert_reqs": ssl.CERT_REQUIRED,
    }


def get_celery_app(settings: WorkerSettings) -> Celery:
    celery_app = Celery("alert_collector", broker=settings.rabbit_mq)
    tls_options = _build_broker_tls_options(settings)
    celery_app.conf.update(
        broker_url=settings.rabbit_mq,
        broker_use_ssl=tls_options,
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
