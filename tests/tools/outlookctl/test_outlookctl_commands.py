from __future__ import annotations

import os

from outlookctl.cli import cli


class TestOutlookctlCommands:
    def test_create_timeblock_non_windows(self, runner) -> None:
        """On macOS/Linux, create_timeblock panics immediately."""
        if os.name == "nt":
            return
        result = runner.invoke(cli, ["create_timeblock"])
        assert result.exit_code != 0 or "only available on Windows" in result.output
