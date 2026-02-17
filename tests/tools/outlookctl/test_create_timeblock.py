from __future__ import annotations

from outlookctl.commands.create_timeblock.create_timeblock import CommandCreateTimeblock


class TestCommandCreateTimeblock:
    def test_init_stores_duration(self) -> None:
        cmd = CommandCreateTimeblock(duration=45)
        assert cmd.duration == 45

    def test_execute_returns_message(self) -> None:
        cmd = CommandCreateTimeblock(duration=60)
        result = cmd.execute()

        assert result.success
        assert result.output == "Would create a timeblock of 60 minutes"
