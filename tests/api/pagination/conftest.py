import pytest

from alert_collector.settings import get_api_settings


@pytest.fixture(autouse=True)
def cursor_hmac_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_HMAC_SECRET", "test-cursor-secret")
    get_api_settings.cache_clear()
    yield
    get_api_settings.cache_clear()
