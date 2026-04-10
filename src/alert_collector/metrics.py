"""Prometheus metrics used by sync and API slices."""

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

try:
    from prometheus_client import Histogram
except ModuleNotFoundError:  # pragma: no cover - optional in local dev
    Histogram = None  # type: ignore[assignment]


if Histogram is not None:
    external_alerts_call_duration_seconds = Histogram(
        "external_alerts_call_duration_seconds",
        "External alerts API call latency in seconds.",
        labelnames=("result",),
    )
else:
    external_alerts_call_duration_seconds = None


@contextmanager
def track_external_alerts_call_duration() -> Iterator[None]:
    """Measure and publish external alerts call duration."""
    started = perf_counter()
    result = "success"
    try:
        yield
    except Exception:
        result = "error"
        raise
    finally:
        if external_alerts_call_duration_seconds is not None:
            elapsed = perf_counter() - started
            external_alerts_call_duration_seconds.labels(result=result).observe(elapsed)
