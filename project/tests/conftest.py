import pytest


@pytest.fixture(autouse=True)
def no_background_sync(monkeypatch):
    """The API's background sync must never reach a real graph database from a test: it is off unless a test builds its own AutoSync with fakes."""
    monkeypatch.setenv("C1_AUTO_SYNC", "0")
