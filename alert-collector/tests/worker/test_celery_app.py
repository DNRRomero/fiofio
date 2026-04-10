import ssl

from alert_collector.settings import WorkerSettings
from alert_collector.worker.celery_app import _build_broker_tls_options, get_celery_app


def _settings(*, rabbit_mq: str) -> WorkerSettings:
    return WorkerSettings(
        RABBIT_MQ=rabbit_mq,
        RABBIT_MQ_TLS_CA_CERT="/tmp/rabbitmq_ca_cert.pem",
        EXTERNAL_SERVICE_HOST="http://external-mock:8000",
        EXTERNAL_SERVICE_TOKEN="token",
        SYNC_FREQUENCY_MINUTES=3,
        MAX_RETRIES=3,
    )


def test_build_broker_tls_options_for_amqps() -> None:
    settings = _settings(rabbit_mq="amqps://user:pass@rabbitmq:5671/%2Falerts")

    assert _build_broker_tls_options(settings) == {
        "ca_certs": "/tmp/rabbitmq_ca_cert.pem",
        "cert_reqs": ssl.CERT_REQUIRED,
    }


def test_build_broker_tls_options_for_amqp() -> None:
    settings = _settings(rabbit_mq="amqp://user:pass@rabbitmq:5672/%2Falerts")

    assert _build_broker_tls_options(settings) is None


def test_get_celery_app_sets_tls_verification_for_amqps() -> None:
    settings = _settings(rabbit_mq="amqps://user:pass@rabbitmq:5671/%2Falerts")

    celery_app = get_celery_app(settings)

    assert celery_app.conf.broker_use_ssl == {
        "ca_certs": "/tmp/rabbitmq_ca_cert.pem",
        "cert_reqs": ssl.CERT_REQUIRED,
    }
