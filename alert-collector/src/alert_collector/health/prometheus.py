"""Prometheus queries used by health evaluation."""

import httpx

EXTERNAL_LATENCY_P95_QUERY = """
histogram_quantile(
  0.95,
  sum by (le) (
    rate(external_alerts_call_duration_seconds_bucket{result="success"}[1h])
  )
)
""".strip()


class PrometheusHealthClient:
    """Read health-related metrics from Prometheus."""

    def __init__(self, *, prometheus_url: str) -> None:
        self._prometheus_url = prometheus_url.rstrip("/")

    def get_external_latency_p95_last_hour(self) -> float:
        """Read the last-hour p95 external call latency from Prometheus."""
        response = httpx.get(
            f"{self._prometheus_url}/api/v1/query",
            params={"query": EXTERNAL_LATENCY_P95_QUERY},
            timeout=5.0,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            raise ValueError("prometheus query did not return success")

        results = payload.get("data", {}).get("result", [])
        if not results:
            return 0.0

        value = results[0].get("value")
        return float(value[1])
