import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest

from alert_collector.api.pagination import (
    CursorPayload,
    CursorSnapshot,
    decode_cursor,
    encode_cursor,
)
from alert_collector.settings import get_api_settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _build_signed_token(*, payload: dict[str, object], secret: str) -> str:
    raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    signature = hmac.new(
        secret.encode("utf-8"), raw_payload, digestmod=hashlib.sha256
    ).digest()
    return f"{_b64url_encode(raw_payload)}.{_b64url_encode(signature)}"


def test_encode_decode_cursor_round_trip() -> None:
    since = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    up_to = since + timedelta(hours=1)
    snapshot = CursorSnapshot(
        since=since.isoformat(), up_to=up_to.isoformat(), severity="high"
    )
    payload = CursorPayload(created_at=up_to, alert_id=42, direction="next")

    token = encode_cursor(payload, snapshot=snapshot)
    decoded = decode_cursor(token, current_snapshot=snapshot)

    assert decoded == payload


@pytest.mark.parametrize(
    ("token", "expected_error"),
    [
        ("missing_separator", "invalid cursor token"),
        ("not-base64.not-base64", "invalid cursor token"),
    ],
)
def test_decode_cursor_rejects_malformed_tokens(
    token: str, expected_error: str
) -> None:
    snapshot = CursorSnapshot(since=None, up_to=None, severity=None)

    with pytest.raises(ValueError, match=expected_error):
        decode_cursor(token, current_snapshot=snapshot)


def test_decode_cursor_rejects_invalid_signature() -> None:
    snapshot = CursorSnapshot(since=None, up_to=None, severity="high")
    payload = CursorPayload(
        created_at=datetime(2026, 1, 1, tzinfo=UTC), alert_id=1, direction="next"
    )
    token = encode_cursor(payload, snapshot=snapshot)
    tampered = f"{token[:-1]}A" if token[-1] != "A" else f"{token[:-1]}B"

    with pytest.raises(ValueError, match="invalid cursor token signature"):
        decode_cursor(tampered, current_snapshot=snapshot)


def test_decode_cursor_rejects_invalid_shape() -> None:
    snapshot = CursorSnapshot(since=None, up_to=None, severity=None)
    token = _build_signed_token(
        payload={
            "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            "direction": "next",
            "id": "1",
            "severity": None,
            "since": None,
            "up_to": None,
        },
        secret="test-cursor-secret",
    )

    with pytest.raises(ValueError, match="cursor token has invalid shape"):
        decode_cursor(token, current_snapshot=snapshot)


def test_decode_cursor_rejects_invalid_timestamp() -> None:
    snapshot = CursorSnapshot(since=None, up_to=None, severity=None)
    token = _build_signed_token(
        payload={
            "created_at": "not-a-timestamp",
            "direction": "next",
            "id": 1,
            "severity": None,
            "since": None,
            "up_to": None,
        },
        secret="test-cursor-secret",
    )

    with pytest.raises(ValueError, match="cursor token contains invalid timestamp"):
        decode_cursor(token, current_snapshot=snapshot)


def test_decode_cursor_rejects_filter_mismatch() -> None:
    snapshot = CursorSnapshot(
        since="2026-01-01T00:00:00+00:00", up_to=None, severity="high"
    )
    payload = CursorPayload(
        created_at=datetime(2026, 1, 1, 0, 30, tzinfo=UTC), alert_id=9, direction="next"
    )
    token = encode_cursor(payload, snapshot=snapshot)

    with pytest.raises(ValueError, match="cursor does not match current query filters"):
        decode_cursor(
            token,
            current_snapshot=CursorSnapshot(
                since="2026-01-01T00:00:00+00:00", up_to=None, severity="low"
            ),
        )
