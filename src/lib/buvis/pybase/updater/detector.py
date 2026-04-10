"""Detect how buvis-gems was installed and map to upgrade commands."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution

__all__ = ["InstallerInfo", "detect_installer"]

_PACKAGE = "buvis-gems"

_STATIC_UPGRADE_COMMANDS: dict[str, tuple[str, ...]] = {
    "uv-tool": ("uv", "tool", "upgrade", _PACKAGE),
    "pipx": ("pipx", "upgrade", _PACKAGE),
    "mise-pipx": ("mise", "upgrade", f"pipx:{_PACKAGE}"),
}

_OVERRIDE_TO_METHOD: dict[str, str] = {
    "uv-tool": "uv-tool",
    "pipx": "pipx",
    "mise-pipx": "mise-pipx",
    "pip": "pip-venv",
    "uv": "uv-venv",
}

_EXTRA_MARKER = re.compile(r"""extra\s*==\s*['"]([^'"]+)['"]""")
_PKG_NAME = re.compile(r"[A-Za-z0-9_.\-]+")


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
        if method is None:
            return _unknown()
        command = _build_upgrade_command(method, _installed_extras(_PACKAGE))
        return InstallerInfo(method=method, upgrade_command=command)

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

    extras = _installed_extras(_PACKAGE)

    for marker, method in _PATH_MARKERS:
        if marker in dist_path:
            return InstallerInfo(method=method, upgrade_command=_build_upgrade_command(method, extras))

    if sys.prefix != sys.base_prefix:
        method = "uv-venv" if installer_name == "uv" else "pip-venv"
        return InstallerInfo(method=method, upgrade_command=_build_upgrade_command(method, extras))

    return _unknown()


def _build_upgrade_command(method: str, extras: tuple[str, ...]) -> tuple[str, ...] | None:
    """Return the upgrade command for ``method``, injecting ``extras`` where needed.

    ``uv-tool``, ``pipx``, and ``mise-pipx`` track the original extras in their
    own receipt, metadata, or config and re-apply them on upgrade, so no extras
    are injected here. The plain ``pip`` and ``uv pip`` upgrade flows have no
    such tracking: upgrading without an explicit ``package[extras]`` spec drops
    any previously installed extras. To keep those installs consistent, pass
    the detected extras through the command.
    """
    static = _STATIC_UPGRADE_COMMANDS.get(method)
    if static is not None:
        return static

    extras_spec = f"[{','.join(extras)}]" if extras else ""
    pkg = f"{_PACKAGE}{extras_spec}"
    if method == "pip-venv":
        return ("pip", "install", "--upgrade", pkg)
    if method == "uv-venv":
        return ("uv", "pip", "install", "--upgrade", pkg)
    return None


def _installed_extras(package: str) -> tuple[str, ...]:
    """Return the declared extras of ``package`` whose dependencies are installed.

    For each name in the distribution's ``Provides-Extra`` metadata, collect the
    requirements tagged with that extra marker and check whether every one of
    them resolves in the current environment. Extras with no tagged
    requirements are skipped because we cannot tell whether they were opted
    into. Returned in declaration order.
    """
    try:
        dist = distribution(package)
    except PackageNotFoundError:
        return ()

    declared = tuple(dist.metadata.get_all("Provides-Extra") or ())
    if not declared:
        return ()

    deps_by_extra: dict[str, list[str]] = {name: [] for name in declared}
    for req in dist.requires or []:
        marker_match = _EXTRA_MARKER.search(req)
        if marker_match is None:
            continue
        extra_name = marker_match.group(1)
        if extra_name not in deps_by_extra:
            continue
        dep_match = _PKG_NAME.match(req)
        if dep_match is not None:
            deps_by_extra[extra_name].append(dep_match.group(0))

    return tuple(
        extra for extra in declared if deps_by_extra[extra] and all(_is_installed(dep) for dep in deps_by_extra[extra])
    )


def _is_installed(pkg_name: str) -> bool:
    try:
        distribution(pkg_name)
    except PackageNotFoundError:
        return False
    return True
