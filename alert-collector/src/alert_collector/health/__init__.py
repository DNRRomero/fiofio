"""Health aggregation package."""

from alert_collector.health.repository import (
    DatabaseProbe,
    HealthRepository,
    WorkerExecutionRecord,
)
from alert_collector.health.prometheus import PrometheusHealthClient
from alert_collector.health.service import HealthReport, HealthService, IngestionError

__all__ = [
    "DatabaseProbe",
    "HealthReport",
    "HealthRepository",
    "HealthService",
    "IngestionError",
    "PrometheusHealthClient",
    "WorkerExecutionRecord",
]
