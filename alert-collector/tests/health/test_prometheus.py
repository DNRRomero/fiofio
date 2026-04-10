import httpx
import respx

from alert_collector.health.prometheus import (
    EXTERNAL_LATENCY_P95_QUERY,
    PrometheusHealthClient,
)


@respx.mock
def test_get_external_latency_p95_last_hour_reads_prometheus_query() -> None:
    route = respx.get("http://prometheus:9090/api/v1/query").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {},
                            "value": [1713000000, "1.2345"],
                        }
                    ],
                },
            },
        )
    )

    client = PrometheusHealthClient(prometheus_url="http://prometheus:9090")

    value = client.get_external_latency_p95_last_hour()

    assert route.called
    assert route.calls[0].request.url.params["query"] == EXTERNAL_LATENCY_P95_QUERY
    assert value == 1.2345


@respx.mock
def test_get_external_latency_p95_last_hour_returns_zero_without_samples() -> None:
    respx.get("http://prometheus:9090/api/v1/query").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [],
                },
            },
        )
    )

    client = PrometheusHealthClient(prometheus_url="http://prometheus:9090")

    value = client.get_external_latency_p95_last_hour()

    assert value == 0.0
