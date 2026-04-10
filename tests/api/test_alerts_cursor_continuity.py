from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from alert_collector.api.app import create_app
from alert_collector.api.pagination import _CURSOR_SNAPSHOT_BY_TOKEN
from alert_collector.db.base import Base
from alert_collector.db.models import Alert


def _make_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def _session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _seed_alerts(session_factory: sessionmaker[Session], now: datetime) -> None:
    with session_factory() as session:
        session.add_all(
            [
                Alert(
                    external_id="a-1",
                    created_at=now - timedelta(minutes=1),
                    severity="high",
                    alert_type="security",
                    message="one",
                    enrichment_ip="10.0.0.1",
                    enrichment_type="random_ipv4",
                    raw_payload={"id": "a-1"},
                ),
                Alert(
                    external_id="a-2",
                    created_at=now - timedelta(minutes=2),
                    severity="high",
                    alert_type="security",
                    message="two",
                    enrichment_ip="10.0.0.2",
                    enrichment_type="random_ipv4",
                    raw_payload={"id": "a-2"},
                ),
                Alert(
                    external_id="a-3",
                    created_at=now - timedelta(minutes=3),
                    severity="low",
                    alert_type="ops",
                    message="three",
                    enrichment_ip="10.0.0.3",
                    enrichment_type="random_ipv4",
                    raw_payload={"id": "a-3"},
                ),
            ]
        )
        session.commit()


def test_cursor_rejects_filter_mismatch(monkeypatch) -> None:
    session_factory = _make_session_factory()
    now = datetime.now(tz=UTC)
    _seed_alerts(session_factory, now)
    _CURSOR_SNAPSHOT_BY_TOKEN.clear()

    monkeypatch.setattr(
        "alert_collector.api.alerts.route.get_session",
        lambda: _session_scope(session_factory),
    )

    client = TestClient(create_app())
    first = client.get("/alerts", params={"severity": "high", "limit": 1})
    assert first.status_code == 200
    cursor = first.json()["next_cursor"]
    assert cursor

    second = client.get("/alerts", params={"severity": "low", "limit": 1, "cursor": cursor})
    assert second.status_code == 422
    assert second.json()["detail"] == "cursor does not match current query filters"


def test_cursor_allows_same_filter_continuation(monkeypatch) -> None:
    session_factory = _make_session_factory()
    now = datetime.now(tz=UTC)
    _seed_alerts(session_factory, now)
    _CURSOR_SNAPSHOT_BY_TOKEN.clear()

    monkeypatch.setattr(
        "alert_collector.api.alerts.route.get_session",
        lambda: _session_scope(session_factory),
    )

    client = TestClient(create_app())
    params = {"severity": "high", "limit": 1}
    first = client.get("/alerts", params=params)
    assert first.status_code == 200

    cursor = first.json()["next_cursor"]
    assert cursor

    second = client.get("/alerts", params={"severity": "high", "limit": 1, "cursor": cursor})
    assert second.status_code == 200
    assert len(second.json()["alerts"]) == 1
