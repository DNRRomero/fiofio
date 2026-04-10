"""Database advisory lock helpers for sync orchestration."""

from hashlib import sha256

from sqlalchemy import text
from sqlalchemy.orm import Session


class SyncLockUnavailableError(Exception):
    """Raised when an advisory lock cannot be acquired."""


def advisory_lock_pair(lock_name: str) -> tuple[int, int]:
    """Map a lock name to two deterministic signed int32 values."""
    digest = sha256(lock_name.encode("utf-8")).digest()
    first = int.from_bytes(digest[0:4], byteorder="big", signed=True)
    second = int.from_bytes(digest[4:8], byteorder="big", signed=True)
    return (first, second)


def acquire_transaction_lock(session: Session, *, lock_name: str = "alerts_sync") -> None:
    """Acquire a Postgres transaction-level advisory lock for sync."""
    key_a, key_b = advisory_lock_pair(lock_name)
    row = session.execute(
        text("SELECT pg_try_advisory_xact_lock(:key_a, :key_b) AS acquired"),
        {"key_a": key_a, "key_b": key_b},
    ).one()
    if not bool(row.acquired):
        raise SyncLockUnavailableError(f"sync lock '{lock_name}' is already held")

