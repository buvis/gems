"""Ask the detected installer's own index which buvis-gems version it would install."""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

from packaging.version import InvalidVersion, Version

from .checker import _query_pypi

if TYPE_CHECKING:
    from pathlib import Path

    from .detector import InstallerInfo

__all__ = ["fetch_installable_version"]

_PACKAGE = "buvis-gems"
_QUERY_TIMEOUT = 10
_UV_COMPILE: tuple[tuple[str, ...], str | None, re.Pattern[str] | None] = (
    ("uv", "pip", "compile", "--no-deps", "--no-header", "--quiet", "-"),
    _PACKAGE,
    re.compile(r"^buvis-gems==(\S+)$", re.M),
)

# method -> (argv, stdin, pattern whose group 1 is the version; None = whole stripped stdout)
_QUERIES: dict[str, tuple[tuple[str, ...], str | None, re.Pattern[str] | None]] = {
    "mise-pipx": (("mise", "latest", f"pipx:{_PACKAGE}"), None, None),
    "pip-venv": (("pip", "index", "versions", _PACKAGE), None, re.compile(r"^buvis-gems \(([^)]+)\)", re.M)),
    "uv-tool": _UV_COMPILE,
    "uv-venv": _UV_COMPILE,
}


def fetch_installable_version(installer: InstallerInfo, state_dir: Path) -> str | None:
    """Return the newest buvis-gems version the detected installer can install.

    Falls back to PyPI for installers without an index query (``pipx``,
    ``unknown``) and whenever the installer query fails. Never raises.

    Args:
        installer: Detected installer info.
        state_dir: Updater state directory, used as the query's working directory
            so uv does not pick up a project config from the caller's cwd.

    Returns:
        A PEP 440 version string, or None when both the installer query and the
        PyPI fallback fail.
    """
    return _query_installer(installer.method, state_dir) or _query_pypi()


def _query_installer(method: str, state_dir: Path) -> str | None:
    query = _QUERIES.get(method)
    if query is None:
        return None
    argv, stdin, pattern = query
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=_QUERY_TIMEOUT,
            cwd=state_dir,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    if pattern is None:
        found = result.stdout.strip()
    else:
        match = pattern.search(result.stdout)
        if match is None:
            return None
        found = match.group(1)
    try:
        Version(found)
    except InvalidVersion:
        return None
    return found
