import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
sys.path.append(str(Path(__file__).resolve().parents[1]))
from domain import Source
from main import app


@pytest.fixture(autouse=True)
def default_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RNG_SEED", raising=False)
    monkeypatch.delenv("FORCE_ERROR", raising=False)
    monkeypatch.setenv("ACCEPTED_TOKEN", "external-mock-token")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def auth_headers(token: str = "external-mock-token") -> dict[str, str]:
    return {"Authorization": f"Token {token}"}


def parse_iso8601_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(UTC)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_alerts_envelope_and_schema(client: TestClient) -> None:
    response = client.get("/alerts/", headers=auth_headers())
    assert response.status_code == 200

    payload = response.json()
    assert "alerts" in payload
    assert isinstance(payload["alerts"], list)
    assert payload["alerts"], "Expected at least one generated alert"

    sample = payload["alerts"][0]
    assert set(sample) == {"id", "source", "severity", "description", "created_at"}
    created_at = parse_iso8601_utc(sample["created_at"])
    assert created_at.tzinfo is UTC


def test_source_filtering(client: TestClient) -> None:
    response = client.get(
        "/alerts/",
        params={"source": ','.join([Source.AWS_GUARDDUTY.value, Source.CLOUDFLARE_WAF.value])},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    alerts = response.json()["alerts"]
    for alert in alerts:
        assert alert["source"] in [Source.AWS_GUARDDUTY.value, Source.CLOUDFLARE_WAF.value]


@pytest.mark.parametrize(
    ("params", "expected_start", "expected_end"),
    [
        (
            {"since": "2026-01-01T00:00:00Z"},
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime.now(UTC),
        ),
        (
            {"up_to": "2026-02-01T00:00:00+00:00"},
            datetime(2026, 1, 2, tzinfo=UTC),
            datetime(2026, 2, 1, tzinfo=UTC),
        ),
        (
            {},
            datetime.now(UTC) - timedelta(days=30),
            datetime.now(UTC),
        ),
    ],
)
def test_optional_window_defaults(
    client: TestClient,
    params: dict[str, str],
    expected_start: datetime,
    expected_end: datetime,
) -> None:
    response = client.get("/alerts/", params=params, headers=auth_headers())
    assert response.status_code == 200
    alerts = response.json()["alerts"]

    drift = timedelta(seconds=5)
    lower_bound = expected_start - drift
    upper_bound = expected_end + drift
    for alert in alerts:
        created_at = parse_iso8601_utc(alert["created_at"])
        assert lower_bound <= created_at <= upper_bound


@pytest.mark.parametrize(
    ("params", "error_substring"),
    [
        ({"source": "bad-source"}, "Invalid source"),
        ({"since": "not-a-date"}, "Invalid datetime"),
        (
            {
                "since": "2026-02-01T00:00:00Z",
                "up_to": "2026-01-01T00:00:00Z",
            },
            "must be less than or equal",
        ),
    ],
)
def test_validation_errors(
    client: TestClient,
    params: dict[str, str],
    error_substring: str,
) -> None:
    response = client.get("/alerts/", params=params, headers=auth_headers())
    assert response.status_code == 422
    assert error_substring in response.json()["detail"]


def test_seeded_rng_can_deterministically_fail(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RNG_SEED", "1")
    response = client.get("/alerts/", headers=auth_headers())
    assert response.status_code == 500


def test_force_error_always_returns_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORCE_ERROR", "true")
    response = client.get("/alerts/", headers=auth_headers())
    assert response.status_code == 500


def test_validation_runs_before_forced_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORCE_ERROR", "true")
    response = client.get("/alerts/", params={"source": "invalid"}, headers=auth_headers())
    assert response.status_code == 422


def test_alerts_returns_401_when_authorization_header_missing(client: TestClient) -> None:
    response = client.get("/alerts/")
    assert response.status_code == 401


def test_alerts_returns_403_when_token_does_not_match(client: TestClient) -> None:
    response = client.get("/alerts/", headers=auth_headers(token="wrong-token"))
    assert response.status_code == 403
