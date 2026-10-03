"""Phase 0: the pure plist and cron renderers (unit-testable off-platform)."""

from __future__ import annotations

import plistlib

import pytest
from klyreon.schedule.cron import MANAGED_MARKER, render_cron_line
from klyreon.schedule.launchd import LABEL, render_plist, scheduled_command

pytestmark = pytest.mark.klyreon


class TestPlist:
    def test_parses_as_plist_and_carries_fields(self) -> None:
        xml = render_plist(binary="/usr/local/bin/klyreon", hour=3, minute=30, path_env="/usr/local/bin:/usr/bin")
        parsed = plistlib.loads(xml.encode("utf-8"))
        assert parsed["Label"] == LABEL
        assert parsed["ProgramArguments"][:2] == ["/bin/sh", "-c"]
        assert parsed["StartCalendarInterval"] == {"Hour": 3, "Minute": 30}
        assert parsed["EnvironmentVariables"]["PATH"] == "/usr/local/bin:/usr/bin"

    def test_command_uses_semicolon_not_and(self) -> None:
        xml = render_plist(binary="/opt/klyreon", hour=0, minute=0, path_env="/bin")
        parsed = plistlib.loads(xml.encode("utf-8"))
        command = parsed["ProgramArguments"][2]
        assert command == "/opt/klyreon ingest; /opt/klyreon maintain"
        assert "&&" not in command

    def test_scheduled_command_shape(self) -> None:
        assert scheduled_command("klyreon") == "klyreon ingest; klyreon maintain"


class TestCronLine:
    def test_carries_marker_binary_and_path(self) -> None:
        fragment = render_cron_line(binary="/usr/local/bin/klyreon", hour=5, minute=15, path_env="/usr/local/bin:/bin")
        lines = fragment.splitlines()
        assert lines[0] == "PATH=/usr/local/bin:/bin " + MANAGED_MARKER
        assert lines[1].startswith(
            "15 5 * * * /bin/sh -c '/usr/local/bin/klyreon ingest; /usr/local/bin/klyreon maintain'"
        )
        assert all(MANAGED_MARKER in ln for ln in lines)

    def test_semicolon_not_and(self) -> None:
        fragment = render_cron_line(binary="klyreon", hour=1, minute=1, path_env="/bin")
        assert "&&" not in fragment
        assert "ingest; " in fragment
