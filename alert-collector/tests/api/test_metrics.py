from importlib.util import find_spec

import pytest
from fastapi.testclient import TestClient

from alert_collector.api.app import create_app

if find_spec("prometheus_client") is None:  # pragma: no cover - environment guard
    pytest.skip("prometheus_client is not installed", allow_module_level=True)


def test_metrics_endpoint_exposes_prometheus_payload() -> None:
    client = TestClient(create_app())

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "external_alerts_call_duration_seconds" in response.text
