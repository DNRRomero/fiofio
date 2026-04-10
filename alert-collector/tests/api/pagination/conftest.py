import pytest


@pytest.fixture(autouse=True)
def cursor_hmac_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_HMAC_SECRET", "test-cursor-secret")
    yield
