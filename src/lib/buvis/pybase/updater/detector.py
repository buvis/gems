"""Detect how buvis-gems was installed and map to upgrade commands."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib.metadata import distribution

__all__ = ["InstallerInfo", "detect_installer"]

_PACKAGE = "buvis-gems"

_OVERRIDE_MAP: dict[str, tuple[str, tuple[str, ...]]] = {
    "uv-tool": ("uv-tool", ("uv", "tool", "upgrade", _PACKAGE)),
    "pipx": ("pipx", ("pipx", "upgrade", _PACKAGE)),
    "pip": ("pip-venv", ("pip", "install", "--upgrade", _PACKAGE)),
    "uv": ("uv-venv", ("uv", "pip", "install", "--upgrade", _PACKAGE)),
}


@dataclass(frozen=True)
class InstallerInfo:
    """Result of installer detection."""

    method: str
    upgrade_command: tuple[str, ...] | None


def _unknown() -> InstallerInfo:
    return InstallerInfo(method="unknown", upgrade_command=None)


_VENV_COMMANDS: dict[str, tuple[str, ...]] = {
    "uv-venv": ("uv", "pip", "install", "--upgrade", _PACKAGE),
    "pip-venv": ("pip", "install", "--upgrade", _PACKAGE),
}


def detect_installer(override: str | None) -> InstallerInfo:
    """Detect the installation method for buvis-gems.

    Args:
        override: Force a specific method (from GlobalSettings.installer).

    Returns:
        InstallerInfo with method name and upgrade command tuple.
    """
    if override is not None:
        pair = _OVERRIDE_MAP.get(override)
        return InstallerInfo(method=pair[0], upgrade_command=pair[1]) if pair else _unknown()

    try:
        dist = distribution(_PACKAGE)
    except Exception:
        return _unknown()

    dist_path = str(getattr(dist, "_path", ""))
    installer_text = dist.read_text("INSTALLER")
    installer_name = installer_text.strip() if installer_text else ""

    if "/uv/tools/" in dist_path:
        return InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", _PACKAGE))

    if "/pipx/venvs/" in dist_path:
        return InstallerInfo(method="pipx", upgrade_command=("pipx", "upgrade", _PACKAGE))

    if sys.prefix != sys.base_prefix:
        method = "uv-venv" if installer_name == "uv" else "pip-venv"
        return InstallerInfo(method=method, upgrade_command=_VENV_COMMANDS[method])

    return _unknown()
