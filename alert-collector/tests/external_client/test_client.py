import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest
import respx

from alert_collector.external_client.client import (
    ExternalAlertsClient,
    ExternalClientError,
    ExternalClientServerError,
)
from alert_collector.external_client.schemas import ExternalAlert

ALERTS_URL = "http://external-mock/alerts/"
SINCE = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)
UP_TO = datetime(2026, 4, 9, 11, 0, tzinfo=UTC)
ResponseBuilder = Callable[[dict[str, Any]], httpx.Response]


def _success_response(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=payload)


def _server_error_response(status_code: int) -> ResponseBuilder:
    def _build(_: dict[str, Any]) -> httpx.Response:
        return httpx.Response(status_code, text="server failure")

    return _build


def _invalid_alert_field_response(field: str, value: str) -> ResponseBuilder:
    def _build(payload: dict[str, Any]) -> httpx.Response:
        bad_payload = copy.deepcopy(payload)
        alerts = bad_payload["alerts"]
        assert isinstance(alerts, list)
        first_alert = alerts[0]
        assert isinstance(first_alert, dict)
        first_alert[field] = value
        return httpx.Response(200, json=bad_payload)

    return _build


@pytest.fixture
def external_alerts_payload() -> dict[str, Any]:
    fixture_path = Path(__file__).parent / "test_data" / "external_alerts_response.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture
def client() -> ExternalAlertsClient:
    return ExternalAlertsClient(
        external_client_host="http://external-mock",
        external_client_token="token",
        timeout_seconds=5.0,
    )


@pytest.mark.parametrize(
    ("response_builder", "expected_error", "expected_status_code"),
    [
        pytest.param(_success_response, None, None, id="success"),
        pytest.param(
            _server_error_response(500), ExternalClientServerError, 500, id="5xx-500"
        ),
        pytest.param(
            _server_error_response(503), ExternalClientServerError, 503, id="5xx-503"
        ),
        pytest.param(
            _invalid_alert_field_response("id", "not-a-uuid"),
            ExternalClientError,
            None,
            id="invalid-payload-id",
        ),
        pytest.param(
            _invalid_alert_field_response("created_at", "not-a-datetime"),
            ExternalClientError,
            None,
            id="invalid-payload-created-at",
        ),
    ],
)
def test_get_alerts_core_behaviors(
    respx_mock: respx.MockRouter,
    client: ExternalAlertsClient,
    external_alerts_payload: dict[str, Any],
    response_builder: ResponseBuilder,
    expected_error: type[ExternalClientError] | None,
    expected_status_code: int | None,
) -> None:
    route = respx_mock.get(ALERTS_URL).mock(
        return_value=response_builder(external_alerts_payload)
    )

    if expected_error is None:
        alerts = client.get_alerts(since=SINCE, up_to=UP_TO)
        expected_alerts = [
            ExternalAlert.model_validate(item)
            for item in external_alerts_payload["alerts"]
        ]
        assert alerts == expected_alerts
    else:
        with pytest.raises(expected_error) as exc_info:
            client.get_alerts(since=SINCE, up_to=UP_TO)
        if expected_status_code is not None:
            assert isinstance(exc_info.value, ExternalClientServerError)
            assert exc_info.value.status_code == expected_status_code

    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer token"
    assert request.headers["Accept"] == "application/json"
    assert request.url.params["since"] == "2026-04-09T10:00:00+00:00"
    assert request.url.params["up_to"] == "2026-04-09T11:00:00+00:00"
