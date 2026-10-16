"""Auto-update checker for buvis-gems CLI tools."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as pkg_version
from typing import TYPE_CHECKING

from buvis.pybase.adapters import console

from .checker import _newer_or_none, check_for_update, fetch_latest_version
from .detector import detect_installer
from .executor import REEXEC_ENV, run_update, run_update_interactive
from .index import fetch_installable_version
from .state import DEFAULT_STATE_DIR, UPGRADE_BACKOFF, append_log, read_upgrade_failure, write_installer_cache

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

    The newest version comes from the detected installer's own index, not PyPI,
    so an index that lags PyPI starts no upgrade.

    Guards:
        - settings.auto_update must be True
        - BUVIS_DEV_MODE must not be "1"
        - the process must not be the restart of an update that already ran
        - an upgrade to the same version must not have been a no-op within UPGRADE_BACKOFF

    Args:
        settings: Resolved GlobalSettings (or subclass) with auto_update and installer fields.
    """
    if not settings.auto_update:
        return

    if os.environ.get("BUVIS_DEV_MODE") == "1":
        return

    if os.environ.get(REEXEC_ENV) == "1":
        return

    try:
        current = pkg_version(_PACKAGE)
    except PackageNotFoundError:
        return

    installer = detect_installer(override=settings.installer)
    latest = check_for_update(
        state_dir=DEFAULT_STATE_DIR,
        fetch=lambda: fetch_installable_version(installer, DEFAULT_STATE_DIR),
        installer_method=installer.method,
    )
    if latest is None or _is_backed_off(latest):
        return

    run_update(current, latest, installer)


def _is_backed_off(latest: str) -> bool:
    """True when upgrading to ``latest`` was a no-op less than UPGRADE_BACKOFF ago."""
    failure = read_upgrade_failure(DEFAULT_STATE_DIR)
    if failure is None:
        return False
    failed_version, failed_at = failure
    return failed_version == latest and datetime.now(tz=timezone.utc) - failed_at < UPGRADE_BACKOFF


def force_update(settings: GlobalSettings) -> int:
    """Run a user-initiated update check and upgrade, bypassing all guards.

    Invoked by the eager ``--update`` CLI flag. Ignores ``settings.auto_update``,
    ``BUVIS_DEV_MODE`` and the upgrade back-off because the user has explicitly
    asked for an update. The target is the newest version the installer's own
    index offers; when PyPI is ahead of it, that lag is reported instead.

    Returns:
        0 when the tool is up to date (including installer index lag) or the
        upgrade succeeds.
        1 on any failure: package not installed, index and PyPI unreachable,
        unknown installer, subprocess failure, or an upgrade that did not apply.
    """
    try:
        current = pkg_version(_PACKAGE)
    except PackageNotFoundError:
        console.failure("buvis-gems is not installed in this environment.")
        append_log(DEFAULT_STATE_DIR, "error", "Force update aborted: buvis-gems not installed")
        return 1

    installer = detect_installer(override=settings.installer)
    latest = fetch_installable_version(installer, DEFAULT_STATE_DIR)
    if latest is None:
        console.failure("Could not reach the installer's index or PyPI to check for updates.")
        append_log(DEFAULT_STATE_DIR, "error", "Force update aborted: installer index and PyPI unreachable")
        return 1
    write_installer_cache(DEFAULT_STATE_DIR, installer.method, latest)

    if _newer_or_none(latest, current) is None:
        pypi = fetch_latest_version(DEFAULT_STATE_DIR)
        if pypi is not None and _newer_or_none(pypi, current) is not None:
            console.success(f"buvis-gems {current} is the newest your installer offers (PyPI has {pypi}).")
            append_log(
                DEFAULT_STATE_DIR,
                "info",
                f"Force update: installer index offers {latest}, PyPI has {pypi} (current {current})",
            )
            return 0
        console.success(f"buvis-gems {current} is up to date.")
        append_log(DEFAULT_STATE_DIR, "info", f"Force update: buvis-gems {current} is up to date")
        return 0

    if installer.upgrade_command is None:
        console.failure(
            f"buvis-gems {latest} is available (current: {current}), "
            "but the installer could not be detected automatically. Upgrade manually with one of:",
            details="\n".join(_MANUAL_UPGRADE_COMMANDS),
        )
        append_log(
            DEFAULT_STATE_DIR,
            "error",
            f"Force update aborted: installer unknown (current {current}, available {latest})",
        )
        return 1

    return run_update_interactive(current, latest, installer)
