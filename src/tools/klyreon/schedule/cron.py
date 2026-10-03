"""The Linux cron artifact: a pure cron-line renderer, unit-testable off-platform.

:func:`render_cron_line` returns the two-line crontab fragment klyreon manages:
an explicit ``PATH=`` assignment and the schedule line, both ending in the
managed marker so the installer can find and strip exactly its own lines. It
touches no ``crontab`` binary; the installer owns the read-strip-append.
"""

from __future__ import annotations

from klyreon.schedule.launchd import scheduled_command

__all__ = ["MANAGED_MARKER", "render_cron_line"]

MANAGED_MARKER = "# klyreon-managed"


def render_cron_line(*, binary: str, hour: int, minute: int, path_env: str) -> str:
    """Render the klyreon-managed crontab fragment.

    Args:
        binary: Absolute path to the ``klyreon`` executable.
        hour: Hour of day, 0-23.
        minute: Minute, 0-59.
        path_env: The ``PATH`` captured at install time. cron runs with a
            minimal environment, so the assignment is what lets the scheduled
            run find ``klyreon`` and the operator CLI it shells out to.

    Returns:
        Two lines: ``PATH=...  # klyreon-managed`` and the schedule line, each
        carrying the marker so a re-install strips exactly these.
    """
    command = scheduled_command(binary)
    path_line = f"PATH={path_env} {MANAGED_MARKER}"
    schedule_line = f"{minute} {hour} * * * /bin/sh -c '{command}' {MANAGED_MARKER}"
    return f"{path_line}\n{schedule_line}"
