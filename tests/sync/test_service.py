from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alert_collector.db.base import Base
from alert_collector.db.models import (
    ALERTS_SINCE_CHECKPOINT_KEY,
    KeyValueState,
    WorkerExecution,
)
from alert_collector.settings import SyncSettings
from alert_collector.sync.locking import SyncLockUnavailableError
from alert_collector.sync.service import SyncExternalFailureError, SyncService


class _StubExternalAlert(BaseModel):
    external_id: str
    created_at: datetime
    severity: str
    alert_type: str
    message: str | None
    raw_payload: dict[str, object]


class _StubExternalClient:
    def __init__(self, alerts: list[_StubExternalAlert]) -> None:
        self._alerts = alerts

    def get_alerts(
        self, *, since: datetime, up_to: datetime
    ) -> list[_StubExternalAlert]:
        del since, up_to
        return self._alerts


class _FailingExternalClient:
    def get_alerts(
        self, *, since: datetime, up_to: datetime
    ) -> list[_StubExternalAlert]:
        del since, up_to
        raise RuntimeError("upstream timeout")


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


def _query_checkpoint(session_factory: sessionmaker[Session]) -> KeyValueState | None:
    with session_factory() as session:
        return session.get(KeyValueState, ALERTS_SINCE_CHECKPOINT_KEY)


def _query_executions(session_factory: sessionmaker[Session]) -> list[WorkerExecution]:
    with session_factory() as session:
        stmt = select(WorkerExecution).order_by(WorkerExecution.attempt_number.asc())
        return session.execute(stmt).scalars().all()


def test_sync_success_writes_execution_and_checkpoint(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
) -> None:
    now = datetime.now(tz=UTC)
    external_alert = _StubExternalAlert(
        external_id="external-1",
        created_at=now - timedelta(minutes=2),
        severity="high",
        alert_type="security",
        message="suspicious login",
        raw_payload={"id": "external-1"},
    )
    service = SyncService(
        session_factory=session_factory,
        external_client=_StubExternalClient([external_alert]),
        settings=SyncSettings(sync_bootstrap_lookback_minutes=15),
    )
    monkeypatch.setattr(
        "alert_collector.sync.service.acquire_transaction_lock",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(service, "_upsert_alerts", lambda session, alerts: None)
    monkeypatch.setattr(
        "alert_collector.sync.service.track_external_alerts_call_duration",
        lambda: nullcontext(),
    )

    result = service.sync_alerts(sync_run_id=uuid4(), attempt_number=1, retry_count=0)

    assert result.checkpoint_updated is True
    checkpoint = _query_checkpoint(session_factory)
    assert checkpoint is not None
    assert datetime.fromisoformat(checkpoint.value).tzinfo is not None

    executions = _query_executions(session_factory)
    assert len(executions) == 1
    assert executions[0].success is True
    assert executions[0].summary is not None
    assert executions[0].summary["checkpoint_updated"] is True


def test_sync_failure_keeps_checkpoint_unchanged_and_records_failed_attempt(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
) -> None:
    seed_checkpoint = datetime.now(tz=UTC) - timedelta(minutes=1)
    with session_factory() as session:
        session.add(
            KeyValueState(
                key=ALERTS_SINCE_CHECKPOINT_KEY,
                value=seed_checkpoint.isoformat(),
            )
        )
        session.commit()

    service = SyncService(
        session_factory=session_factory,
        external_client=_FailingExternalClient(),
        settings=SyncSettings(sync_bootstrap_lookback_minutes=15),
    )
    monkeypatch.setattr(
        "alert_collector.sync.service.acquire_transaction_lock",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "alert_collector.sync.service.track_external_alerts_call_duration",
        lambda: nullcontext(),
    )

    with pytest.raises(SyncExternalFailureError):
        service.sync_alerts(sync_run_id=uuid4(), attempt_number=1, retry_count=0)

    checkpoint = _query_checkpoint(session_factory)
    assert checkpoint is not None
    assert checkpoint.value == seed_checkpoint.isoformat()

    executions = _query_executions(session_factory)
    assert len(executions) == 1
    assert executions[0].success is False
    assert executions[0].error_type == "RuntimeError"


def test_checkpoint_update_is_monotonic(session_factory: sessionmaker[Session]) -> None:
    service = SyncService(
        session_factory=session_factory,
        external_client=_StubExternalClient([]),
        settings=SyncSettings(sync_bootstrap_lookback_minutes=15),
    )
    baseline = datetime.now(tz=UTC)

    with session_factory() as session:
        session.add(
            KeyValueState(key=ALERTS_SINCE_CHECKPOINT_KEY, value=baseline.isoformat())
        )
        session.commit()

    with session_factory() as session:
        with session.begin():
            updated = service._update_checkpoint_monotonic(
                session, up_to=baseline - timedelta(seconds=1)
            )
        assert updated is False

    checkpoint = _query_checkpoint(session_factory)
    assert checkpoint is not None
    assert checkpoint.value == baseline.isoformat()


def test_lock_failure_prevents_side_effects(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
) -> None:
    service = SyncService(
        session_factory=session_factory,
        external_client=_StubExternalClient([]),
        settings=SyncSettings(sync_bootstrap_lookback_minutes=15),
    )
    monkeypatch.setattr(
        "alert_collector.sync.service.acquire_transaction_lock",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SyncLockUnavailableError("locked")
        ),
    )

    with pytest.raises(SyncLockUnavailableError):
        service.sync_alerts(sync_run_id=uuid4(), attempt_number=1, retry_count=0)

    assert _query_checkpoint(session_factory) is None
    assert _query_executions(session_factory) == []
