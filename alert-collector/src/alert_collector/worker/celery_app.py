"""Celery application wiring."""

import ssl

from celery import Celery
from kombu import Exchange, Queue

from alert_collector.settings import WorkerSettings
from alert_collector.worker.scheduler import build_beat_schedule
from alert_collector.worker.tasks import sync_alerts_task

DEFAULT_QUEUE = "alert-collector"
DEFAULT_EXCHANGE = "alert-collector"
DLX_EXCHANGE = "alert-collector.dlx"
DLQ_QUEUE = "alert-collector.dlq"
DLQ_ROUTING_KEY = "alert-collector.dead"


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
    default_exchange = Exchange(DEFAULT_EXCHANGE, type="direct")
    dead_letter_exchange = Exchange(DLX_EXCHANGE, type="direct")
    celery_app.conf.update(
        broker_url=settings.rabbit_mq,
        broker_use_ssl=tls_options,
        task_default_queue=DEFAULT_QUEUE,
        task_default_exchange=DEFAULT_EXCHANGE,
        task_default_routing_key=DEFAULT_QUEUE,
        task_queues=(
            Queue(
                DEFAULT_QUEUE,
                exchange=default_exchange,
                routing_key=DEFAULT_QUEUE,
                queue_arguments={
                    "x-dead-letter-exchange": DLX_EXCHANGE,
                    "x-dead-letter-routing-key": DLQ_ROUTING_KEY,
                },
            ),
            Queue(
                DLQ_QUEUE,
                exchange=dead_letter_exchange,
                routing_key=DLQ_ROUTING_KEY,
            ),
        ),
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        timezone="UTC",
        enable_utc=True,
        beat_schedule=build_beat_schedule(settings),
        imports=("alert_collector.worker.tasks",),
    )
    celery_app.task(
        bind=True, name="alert_collector.sync_alerts", max_retries=settings.max_retries
    )(sync_alerts_task)
    return celery_app
