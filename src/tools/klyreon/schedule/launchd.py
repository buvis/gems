"""The macOS launchd artifact: a pure plist renderer, unit-testable off-platform.

:func:`render_plist` returns the XML text for a ``LaunchAgent`` that runs
``/bin/sh -c '<klyreon> ingest; <klyreon> maintain'`` daily at ``HH:MM`` with an
explicit ``PATH``. It touches no filesystem and no ``launchctl``, so the test
matrix exercises it on Linux too. The installer owns the bootstrap/bootout and
the file write.

The label is namespaced ``net.buvis.klyreon`` so a bootout targets exactly
klyreon's agent and never another LaunchAgent.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

__all__ = ["LABEL", "render_plist", "scheduled_command"]

LABEL = "net.buvis.klyreon"


def scheduled_command(binary: str) -> str:
    """Return the ``ingest; maintain`` shell command for ``binary``.

    A semicolon, not ``&&``: a failed ingest (a bad source) must never stop the
    maintenance pass that follows it.
    """
    return f"{binary} ingest; {binary} maintain"


def render_plist(*, binary: str, hour: int, minute: int, path_env: str) -> str:
    """Render the LaunchAgent plist XML.

    Args:
        binary: Absolute path to the ``klyreon`` executable.
        hour: Hour of day, 0-23.
        minute: Minute, 0-59.
        path_env: The ``PATH`` captured at install time, injected so the
            scheduled run finds ``klyreon`` and whatever it shells out to.
    """
    command = scheduled_command(binary)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "  <key>Label</key>\n"
        f"  <string>{escape(LABEL)}</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        "    <string>/bin/sh</string>\n"
        "    <string>-c</string>\n"
        f"    <string>{escape(command)}</string>\n"
        "  </array>\n"
        "  <key>EnvironmentVariables</key>\n"
        "  <dict>\n"
        "    <key>PATH</key>\n"
        f"    <string>{escape(path_env)}</string>\n"
        "  </dict>\n"
        "  <key>StartCalendarInterval</key>\n"
        "  <dict>\n"
        "    <key>Hour</key>\n"
        f"    <integer>{hour}</integer>\n"
        "    <key>Minute</key>\n"
        f"    <integer>{minute}</integer>\n"
        "  </dict>\n"
        "  <key>RunAtLoad</key>\n"
        "  <false/>\n"
        "</dict>\n"
        "</plist>\n"
    )
