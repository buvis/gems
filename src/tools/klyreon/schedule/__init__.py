"""The scheduler: klyreon's external trigger, since there is no daemon.

Two pure renderers (:func:`klyreon.schedule.launchd.render_plist`,
:func:`klyreon.schedule.cron.render_cron_line`) that are unit-testable
off-platform, and a platform-dispatched installer
(:mod:`klyreon.schedule.installer`) that writes, inspects, and removes the
artifact and records it in PRD C's manifest with ``kind: schedule``.

The scheduled command is ``/bin/sh -c '<klyreon> ingest; <klyreon> maintain'``
— a semicolon so a failed source never stops maintenance — and both artifacts
carry an explicit ``PATH`` captured at install time, because neither cron nor
launchd inherits a login shell's PATH.
"""

from __future__ import annotations

from klyreon.schedule.cron import render_cron_line
from klyreon.schedule.installer import (
    LABEL,
    MANAGED_MARKER,
    ScheduleInfo,
    ScheduleResult,
    UnsupportedPlatformError,
    install,
    status,
    uninstall,
)
from klyreon.schedule.launchd import render_plist

__all__ = [
    "LABEL",
    "MANAGED_MARKER",
    "ScheduleInfo",
    "ScheduleResult",
    "UnsupportedPlatformError",
    "install",
    "render_cron_line",
    "render_plist",
    "status",
    "uninstall",
]
