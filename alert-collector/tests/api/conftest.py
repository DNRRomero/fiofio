import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alert_collector.api.app import create_app
from alert_collector.auth.users import current_active_user
from alert_collector.db.models.user import User as UserModel
from alert_collector.sync.service import SyncService


@pytest.fixture(autouse=True)
def _configure_api_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTERNAL_SERVICE_HOST", "http://external.mock")
    monkeypatch.setenv("EXTERNAL_SERVICE_TOKEN", "test-token")
    SyncService._instances.pop(SyncService, None)


@pytest.fixture()
def mock_user() -> UserModel:
    return UserModel(
        id=1,
        email="test@test.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )


@pytest.fixture()
def app(mock_user: UserModel) -> FastAPI:
    application = create_app()
    application.dependency_overrides[current_active_user] = lambda: mock_user
    yield application
    application.dependency_overrides.clear()


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)
