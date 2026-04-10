"""Cursor pagination utilities."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from threading import Lock


@dataclass(frozen=True, slots=True)
class CursorPayload:
    """Cursor payload data encoded in the opaque token."""

    created_at: datetime
    alert_id: int
    direction: str


@dataclass(frozen=True, slots=True)
class CursorSnapshot:
    """Request filters snapshot associated with a cursor token."""

    since: str | None
    up_to: str | None
    severity: str | None


_CURSOR_SNAPSHOT_BY_TOKEN: dict[str, CursorSnapshot] = {}
_SNAPSHOT_LOCK = Lock()


def snapshot_from_filters(*, since: datetime | None, up_to: datetime | None, severity: str | None) -> CursorSnapshot:
    """Build a normalized cursor snapshot from query filters."""
    return CursorSnapshot(
        since=since.isoformat() if since is not None else None,
        up_to=up_to.isoformat() if up_to is not None else None,
        severity=severity,
    )


def encode_cursor(payload: CursorPayload) -> str:
    """Encode a cursor payload into an opaque token."""
    raw = json.dumps(
        {"created_at": payload.created_at.isoformat(), "id": payload.alert_id, "direction": payload.direction},
        separators=(",", ":"),
    ).encode("utf-8")
    token = base64.urlsafe_b64encode(raw).decode("utf-8")
    return token.rstrip("=")


def decode_cursor(token: str) -> CursorPayload:
    """Decode a cursor token into a typed payload."""
    padded = token + "=" * (-len(token) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid cursor token") from exc

    created_at_raw = payload.get("created_at")
    alert_id = payload.get("id")
    direction = payload.get("direction")
    if not isinstance(created_at_raw, str) or not isinstance(alert_id, int) or not isinstance(direction, str):
        raise ValueError("cursor token has invalid shape")

    try:
        created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("cursor token contains invalid timestamp") from exc

    return CursorPayload(created_at=created_at, alert_id=alert_id, direction=direction)


def register_cursor_snapshot(*, token: str, snapshot: CursorSnapshot) -> None:
    """Persist request continuity snapshot for cursor validation."""
    with _SNAPSHOT_LOCK:
        _CURSOR_SNAPSHOT_BY_TOKEN[token] = snapshot


def assert_cursor_continuity(*, token: str, current_snapshot: CursorSnapshot) -> None:
    """Validate cursor is reused with the same filters as when generated."""
    with _SNAPSHOT_LOCK:
        original = _CURSOR_SNAPSHOT_BY_TOKEN.get(token)

    if original is None:
        raise ValueError("unknown or expired cursor")
    if original != current_snapshot:
        raise ValueError("cursor does not match current query filters")

