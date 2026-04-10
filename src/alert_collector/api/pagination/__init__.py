"""Cursor pagination utilities."""

import base64
import hashlib
import hmac
import json
from datetime import datetime

from pydantic import BaseModel


class CursorPayload(BaseModel):
    """Cursor payload data encoded in the opaque token."""

    created_at: datetime
    alert_id: int
    direction: str


class CursorSnapshot(BaseModel):
    """Request filters snapshot associated with a cursor token."""

    since: str | None
    up_to: str | None
    severity: str | None


def snapshot_from_filters(
    *, since: datetime | None, up_to: datetime | None, severity: str | None
) -> CursorSnapshot:
    """Build a normalized cursor snapshot from query filters."""
    return CursorSnapshot(
        since=since.isoformat() if since is not None else None,
        up_to=up_to.isoformat() if up_to is not None else None,
        severity=severity,
    )


def _b64url_encode(raw: bytes) -> str:
    """Encode bytes with URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    """Decode URL-safe base64 bytes with optional padding."""
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _canonical_payload_bytes(payload: dict[str, object]) -> bytes:
    """Serialize cursor payload into canonical JSON bytes."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def encode_cursor(
    hmac_secret: str, payload: CursorPayload, *, snapshot: CursorSnapshot
) -> str:
    """Encode a self-contained cursor token signed with HMAC-SHA256."""
    raw_payload = _canonical_payload_bytes(
        {
            "created_at": payload.created_at.isoformat(),
            "direction": payload.direction,
            "id": payload.alert_id,
            "severity": snapshot.severity,
            "since": snapshot.since,
            "up_to": snapshot.up_to,
        }
    )
    signature = hmac.new(
        hmac_secret.encode("utf-8"), raw_payload, digestmod=hashlib.sha256
    ).digest()
    return f"{_b64url_encode(raw_payload)}.{_b64url_encode(signature)}"


def decode_cursor(
    hmac_secret: str, token: str, *, current_snapshot: CursorSnapshot
) -> CursorPayload:
    """Decode and validate a signed cursor token including filter continuity."""
    parts = token.split(".", maxsplit=1)
    if len(parts) != 2:
        raise ValueError("invalid cursor token")

    payload_part, signature_part = parts
    try:
        raw_payload = _b64url_decode(payload_part)
        token_signature = _b64url_decode(signature_part)
        payload = json.loads(raw_payload.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid cursor token") from exc

    expected_signature = hmac.new(
        hmac_secret.encode("utf-8"), raw_payload, digestmod=hashlib.sha256
    ).digest()
    if not hmac.compare_digest(token_signature, expected_signature):
        raise ValueError("invalid cursor token signature")

    created_at_raw = payload.get("created_at")
    alert_id = payload.get("id")
    direction = payload.get("direction")
    since = payload.get("since")
    up_to = payload.get("up_to")
    severity = payload.get("severity")
    if (
        not isinstance(created_at_raw, str)
        or not isinstance(alert_id, int)
        or not isinstance(direction, str)
        or (since is not None and not isinstance(since, str))
        or (up_to is not None and not isinstance(up_to, str))
        or (severity is not None and not isinstance(severity, str))
    ):
        raise ValueError("cursor token has invalid shape")

    try:
        created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("cursor token contains invalid timestamp") from exc

    if CursorSnapshot(since=since, up_to=up_to, severity=severity) != current_snapshot:
        raise ValueError("cursor does not match current query filters")

    return CursorPayload(created_at=created_at, alert_id=alert_id, direction=direction)
