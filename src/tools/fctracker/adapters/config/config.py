from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fctracker.settings import FctrackerSettings


@lru_cache
def get_settings() -> FctrackerSettings:
    """Lazy-load settings on first access."""
    return FctrackerSettings()


class FCTrackerConfig:
    """Wrapper providing dict-style access to settings for backwards compatibility."""

    @property
    def local_currency(self: FCTrackerConfig) -> dict[str, str | int]:
        settings = get_settings()
        return {
            "code": settings.local_currency.code,
            "symbol": settings.local_currency.symbol,
            "precision": settings.local_currency.precision,
        }

    @property
    def currency(self: FCTrackerConfig) -> dict[str, dict[str, str | int]]:
        settings = get_settings()
        return {
            code: {
                "symbol": fc.symbol,
                "precision": fc.precision,
            }
            for code, fc in settings.foreign_currencies.items()
        }

    @property
    def transactions_dir(self: FCTrackerConfig) -> Path:
        settings = get_settings()
        if not settings.transactions_dir:
            raise FileNotFoundError("transactions_dir not configured")
        return Path(settings.transactions_dir).expanduser().resolve()


cfg = FCTrackerConfig()
