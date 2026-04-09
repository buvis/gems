"""Check PyPI for newer versions with local caching."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.metadata import version as pkg_version
from pathlib import Path
from urllib.request import Request, urlopen

from packaging.version import Version

__all__ = ["check_for_update"]

_PACKAGE = "buvis-gems"
_PYPI_URL = f"https://pypi.org/pypi/{_PACKAGE}/json"
_CACHE_FILE = ".update_cache.json"
_TIMEOUT_SECONDS = 3


def _read_cache(cache_dir: Path) -> tuple[datetime | None, str | None]:
    """Read cached check timestamp and version. Returns (None, None) on any error."""
    cache_path = cache_dir / _CACHE_FILE
    try:
        data = json.loads(cache_path.read_text())
        last_check = datetime.fromisoformat(data["last_check"])
        if last_check.tzinfo is None:
            last_check = last_check.replace(tzinfo=timezone.utc)
        return last_check, data["latest_version"]
    except Exception:
        return None, None


def _write_cache(cache_dir: Path, latest_version: str) -> None:
    """Write check timestamp and version to cache. Silently ignores errors."""
    cache_path = cache_dir / _CACHE_FILE
    try:
        cache_path.write_text(
            json.dumps(
                {
                    "last_check": datetime.now(tz=timezone.utc).isoformat(),
                    "latest_version": latest_version,
                }
            )
        )
    except Exception:
        return


def _query_pypi() -> str | None:
    """Fetch latest stable version from PyPI. Returns None on any error."""
    try:
        req = Request(_PYPI_URL, headers={"Accept": "application/json"})
        with urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read())
            version: str = data["info"]["version"]
            return version
    except Exception:
        return None


def _newer_or_none(latest: str, current: str) -> str | None:
    """Return latest if strictly newer than current (PEP 440), else None."""
    try:
        return latest if Version(latest) > Version(current) else None
    except Exception:
        return None


def check_for_update(
    cache_dir: Path | None = None,
    interval_hours: int = 6,
) -> str | None:
    """Check if a newer stable version of buvis-gems is available.

    Args:
        cache_dir: Directory for cache file. Defaults to ~/.config/buvis.
        interval_hours: Hours between PyPI checks. 0 means always check.

    Returns:
        Latest version string if newer than current, None otherwise.
    """
    try:
        current = pkg_version(_PACKAGE)
    except Exception:
        return None

    if cache_dir is None:
        cache_dir = Path.home() / ".config" / "buvis"

    last_check, cached_version = _read_cache(cache_dir)
    now = datetime.now(tz=timezone.utc)

    cache_is_fresh = (
        last_check is not None and interval_hours > 0 and (now - last_check).total_seconds() < interval_hours * 3600
    )

    if cache_is_fresh and cached_version is not None:
        return _newer_or_none(cached_version, current)

    pypi_version = _query_pypi()
    if pypi_version is None:
        return None

    _write_cache(cache_dir, pypi_version)
    return _newer_or_none(pypi_version, current)
