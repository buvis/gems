"""Check PyPI for newer versions with local caching."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.metadata import version as pkg_version
from pathlib import Path
from urllib.request import Request, urlopen

from packaging.version import Version

from .state import DEFAULT_STATE_DIR, read_cache, write_cache

__all__ = ["check_for_update"]

_PACKAGE = "buvis-gems"
_PYPI_URL = f"https://pypi.org/pypi/{_PACKAGE}/json"
_TIMEOUT_SECONDS = 3


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
    state_dir: Path | None = None,
    interval_hours: int = 6,
) -> str | None:
    """Check if a newer stable version of buvis-gems is available.

    Args:
        state_dir: Directory for the updater state file. Defaults to ~/.config/buvis.
        interval_hours: Hours between PyPI checks. 0 means always check.

    Returns:
        Latest version string if newer than current, None otherwise.
    """
    try:
        current = pkg_version(_PACKAGE)
    except Exception:
        return None

    if state_dir is None:
        state_dir = DEFAULT_STATE_DIR

    last_check, cached_version = read_cache(state_dir)
    now = datetime.now(tz=timezone.utc)

    cache_is_fresh = (
        last_check is not None and interval_hours > 0 and (now - last_check).total_seconds() < interval_hours * 3600
    )

    if cache_is_fresh and cached_version is not None:
        return _newer_or_none(cached_version, current)

    pypi_version = _query_pypi()
    if pypi_version is None:
        return None

    write_cache(state_dir, pypi_version)
    return _newer_or_none(pypi_version, current)
