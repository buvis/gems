"""Check for newer versions (PyPI or a caller-supplied source) with local caching."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.request import Request, urlopen

from packaging.version import Version

from .state import DEFAULT_STATE_DIR, read_cache, read_installer_cache, write_cache, write_installer_cache

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["check_for_update", "fetch_latest_version"]

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
    fetch: Callable[[], str | None] | None = None,
    *,
    installer_method: str | None = None,
) -> str | None:
    """Check if a newer stable version of buvis-gems is available.

    Args:
        state_dir: Directory for the updater state file. Defaults to ~/.config/buvis.
        interval_hours: Hours between checks. 0 means always check.
        fetch: Zero-argument version source called on a cache miss. None queries PyPI.
        installer_method: When set, read and write only the installer cache recorded
            for this method, never the top-level PyPI cache.

    Returns:
        Latest version string if newer than current, None otherwise.
    """
    try:
        current = pkg_version(_PACKAGE)
    except Exception:
        return None

    if state_dir is None:
        state_dir = DEFAULT_STATE_DIR

    if installer_method is None:
        last_check, cached_version = read_cache(state_dir)
    else:
        last_check, cached_version = read_installer_cache(state_dir, installer_method)
    now = datetime.now(tz=timezone.utc)

    cache_is_fresh = (
        last_check is not None and interval_hours > 0 and (now - last_check).total_seconds() < interval_hours * 3600
    )

    if cache_is_fresh and cached_version is not None:
        return _newer_or_none(cached_version, current)

    latest_version = (fetch or _query_pypi)()
    if latest_version is None:
        return None

    if installer_method is None:
        write_cache(state_dir, latest_version)
    else:
        write_installer_cache(state_dir, installer_method, latest_version)
    return _newer_or_none(latest_version, current)


def fetch_latest_version(state_dir: Path | None = None) -> str | None:
    """Query PyPI unconditionally for the latest stable version.

    Bypasses cache freshness (used by the user-initiated `--update` flow to
    report installer index lag). Writes through to the top-level PyPI cache only,
    never to the installer cache that passive checks read.

    Args:
        state_dir: Directory for the updater state file. Defaults to ~/.config/buvis.

    Returns:
        The latest version string from PyPI, or None on any network/parse error.
    """
    if state_dir is None:
        state_dir = DEFAULT_STATE_DIR

    pypi_version = _query_pypi()
    if pypi_version is None:
        return None

    write_cache(state_dir, pypi_version)
    return pypi_version
