"""Detect how buvis-gems was installed and map to upgrade commands."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib.metadata import distribution

__all__ = ["InstallerInfo", "detect_installer"]

_PACKAGE = "buvis-gems"

_UPGRADE_COMMANDS: dict[str, tuple[str, ...]] = {
    "uv-tool": ("uv", "tool", "upgrade", _PACKAGE),
    "pipx": ("pipx", "upgrade", _PACKAGE),
    "mise-pipx": ("mise", "upgrade", f"pipx:{_PACKAGE}"),
    "pip-venv": ("pip", "install", "--upgrade", _PACKAGE),
    "uv-venv": ("uv", "pip", "install", "--upgrade", _PACKAGE),
}

_OVERRIDE_TO_METHOD: dict[str, str] = {
    "uv-tool": "uv-tool",
    "pipx": "pipx",
    "mise-pipx": "mise-pipx",
    "pip": "pip-venv",
    "uv": "uv-venv",
}


@dataclass(frozen=True)
class InstallerInfo:
    """Result of installer detection."""

    method: str
    upgrade_command: tuple[str, ...] | None


def _unknown() -> InstallerInfo:
    return InstallerInfo(method="unknown", upgrade_command=None)


def detect_installer(override: str | None) -> InstallerInfo:
    """Detect the installation method for buvis-gems.

    Args:
        override: Force a specific method (from GlobalSettings.installer).

    Returns:
        InstallerInfo with method name and upgrade command tuple.
    """
    if override is not None:
        method = _OVERRIDE_TO_METHOD.get(override)
        return InstallerInfo(method=method, upgrade_command=_UPGRADE_COMMANDS[method]) if method else _unknown()

    try:
        dist = distribution(_PACKAGE)
    except Exception:
        return _unknown()

    dist_path = str(getattr(dist, "_path", ""))
    installer_text = dist.read_text("INSTALLER")
    installer_name = installer_text.strip() if installer_text else ""

    _PATH_MARKERS: tuple[tuple[str, str], ...] = (
        ("/uv/tools/", "uv-tool"),
        ("/mise/installs/pipx-", "mise-pipx"),
        ("/pipx/venvs/", "pipx"),
    )

    for marker, method in _PATH_MARKERS:
        if marker in dist_path:
            return InstallerInfo(method=method, upgrade_command=_UPGRADE_COMMANDS[method])

    if sys.prefix != sys.base_prefix:
        method = "uv-venv" if installer_name == "uv" else "pip-venv"
        return InstallerInfo(method=method, upgrade_command=_UPGRADE_COMMANDS[method])

    return _unknown()
