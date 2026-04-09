"""Auto-update checker for buvis-gems CLI tools."""

from __future__ import annotations

import os
from importlib.metadata import version as pkg_version
from typing import TYPE_CHECKING

from .checker import check_for_update
from .detector import detect_installer
from .executor import run_update

if TYPE_CHECKING:
    from buvis.pybase.configuration.settings import GlobalSettings

__all__ = ["check_and_update"]

_PACKAGE = "buvis-gems"


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

    current = pkg_version(_PACKAGE)
    installer = detect_installer(override=settings.installer)
    run_update(current, latest, installer)
