"""Auto-update checker for buvis-gems CLI tools."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import TYPE_CHECKING

import click
from packaging.version import Version

from .checker import check_for_update, fetch_latest_version
from .detector import detect_installer
from .executor import run_update, run_update_interactive
from .state import DEFAULT_STATE_DIR, append_log

if TYPE_CHECKING:
    from buvis.pybase.configuration.settings import GlobalSettings

__all__ = ["check_and_update", "force_update"]

_PACKAGE = "buvis-gems"

_MANUAL_UPGRADE_COMMANDS = (
    "uv tool upgrade buvis-gems",
    "pipx upgrade buvis-gems",
    "mise upgrade pipx:buvis-gems",
)


def check_and_update(settings: GlobalSettings) -> None:
    """Check for updates and auto-upgrade if possible.

    Guards:
        - settings.auto_update must be True
        - BUVIS_DEV_MODE must not be "1"

    Args:
        settings: Resolved GlobalSettings (or subclass) with auto_update and installer fields.
    """
    if not settings.auto_update:
        return

    if os.environ.get("BUVIS_DEV_MODE") == "1":
        return

    latest = check_for_update()
    if latest is None:
        return

    try:
        current = pkg_version(_PACKAGE)
    except PackageNotFoundError:
        return

    installer = detect_installer(override=settings.installer)
    run_update(current, latest, installer)


def force_update(settings: GlobalSettings) -> int:
    """Run a user-initiated update check and upgrade, bypassing all guards.

    Invoked by the eager ``--update`` CLI flag. Ignores ``settings.auto_update``
    and ``BUVIS_DEV_MODE`` because the user has explicitly asked for an update.

    Returns:
        0 when the tool is up to date or the upgrade succeeds.
        1 on any failure: package not installed, PyPI unreachable, unknown
        installer, or subprocess failure.
    """
    try:
        current = pkg_version(_PACKAGE)
    except PackageNotFoundError:
        click.echo("buvis-gems is not installed in this environment.", err=True)
        append_log(DEFAULT_STATE_DIR, "error", "Force update aborted: buvis-gems not installed")
        return 1

    latest = fetch_latest_version()
    if latest is None:
        click.echo("Could not reach PyPI to check for updates.", err=True)
        append_log(DEFAULT_STATE_DIR, "error", "Force update aborted: PyPI unreachable")
        return 1

    if Version(latest) <= Version(current):
        click.echo(f"buvis-gems {current} is up to date.")
        append_log(DEFAULT_STATE_DIR, "info", f"Force update: buvis-gems {current} is up to date")
        return 0

    installer = detect_installer(override=settings.installer)
    if installer.upgrade_command is None:
        click.echo(
            f"buvis-gems {latest} is available (current: {current}), "
            "but the installer could not be detected automatically.\n"
            "Upgrade manually with one of:",
            err=True,
        )
        for cmd in _MANUAL_UPGRADE_COMMANDS:
            click.echo(f"  {cmd}", err=True)
        append_log(
            DEFAULT_STATE_DIR,
            "error",
            f"Force update aborted: installer unknown (current {current}, available {latest})",
        )
        return 1

    return run_update_interactive(current, latest, installer)
