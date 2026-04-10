from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


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
                ),
                Alert(
                    external_id="a-2",
                    created_at=now - timedelta(minutes=1),
                    severity="high",
                    alert_type="security",
                    message="two",
                    enrichment_ip="10.0.0.2",
                    enrichment_type="random_ipv4",
                ),
                Alert(
                    external_id="a-3",
                    created_at=now - timedelta(minutes=3),
                    severity="low",
                    alert_type="ops",
                    message="three",
                    enrichment_ip="10.0.0.3",
                    enrichment_type="random_ipv4",
                ),
            ]
        )
        session.commit()


def test_cursor_orders_by_created_at_then_id(client: TestClient, monkeypatch) -> None:
    session_factory = _make_session_factory()
    now = datetime.now(tz=UTC)
    _seed_alerts(session_factory, now)

    monkeypatch.setattr(
        "alert_collector.api.alerts.app.get_session",
        lambda: _session_scope(session_factory),
    )

    first = client.get("/alerts", params={"size": 2})
    assert first.status_code == 200
    first_payload = first.json()
    assert "current_page" not in first_payload
    assert "current_page_backwards" not in first_payload
    assert [item["external_id"] for item in first_payload["alerts"]] == ["a-2", "a-1"]
    cursor = first_payload["next_page"]
    assert cursor

    second = client.get("/alerts", params={"size": 2, "cursor": cursor})
    assert second.status_code == 200
    second_payload = second.json()
    assert [item["external_id"] for item in second_payload["alerts"]] == ["a-3"]
    assert second_payload["next_page"] is None


def test_cursor_does_not_bind_query_filters(client: TestClient, monkeypatch) -> None:
    session_factory = _make_session_factory()
    now = datetime.now(tz=UTC)
    _seed_alerts(session_factory, now)

    monkeypatch.setattr(
        "alert_collector.api.alerts.app.get_session",
        lambda: _session_scope(session_factory),
    )

    params = {"severity": "high", "size": 1}
    first = client.get("/alerts", params=params)
    assert first.status_code == 200

    cursor = first.json()["next_page"]
    assert cursor

    second = client.get(
        "/alerts", params={"severity": "low", "size": 1, "cursor": cursor}
    )
    assert second.status_code == 200
    assert len(second.json()["alerts"]) <= 1


def test_cursor_rejects_invalid_shape(client: TestClient, monkeypatch) -> None:
    session_factory = _make_session_factory()
    now = datetime.now(tz=UTC)
    _seed_alerts(session_factory, now)

    monkeypatch.setattr(
        "alert_collector.api.alerts.app.get_session",
        lambda: _session_scope(session_factory),
    )

    response = client.get(
        "/alerts", params={"severity": "high", "size": 1, "cursor": "_w=="}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid cursor value"
