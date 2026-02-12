import pytest


@pytest.fixture(autouse=True)
def fctracker_env(monkeypatch):
    """Set env vars so cfg resolves EUR with expected symbol/precision."""
    monkeypatch.setenv("BUVIS_FCTRACKER_LOCAL_CURRENCY__CODE", "CZK")
    monkeypatch.setenv("BUVIS_FCTRACKER_LOCAL_CURRENCY__SYMBOL", "Kč")
    monkeypatch.setenv("BUVIS_FCTRACKER_LOCAL_CURRENCY__PRECISION", "2")
    monkeypatch.setenv(
        "BUVIS_FCTRACKER_FOREIGN_CURRENCIES",
        '{"EUR": {"symbol": "€", "precision": 2}, "USD": {"symbol": "$", "precision": 2}}',
    )
    # Clear the lru_cache so settings are re-read with new env vars
    from fctracker.adapters.config.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
