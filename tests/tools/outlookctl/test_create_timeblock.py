from __future__ import annotations

from unittest.mock import patch

from outlookctl.commands.create_timeblock.create_timeblock import CommandCreateTimeblock


class TestCommandCreateTimeblockInit:
    def test_init_stores_duration(self) -> None:
        with patch("outlookctl.commands.create_timeblock.create_timeblock.os.name", "posix"), patch(
            "outlookctl.commands.create_timeblock.create_timeblock.console.warning"
        ):
            cmd = CommandCreateTimeblock(duration=45)

        assert cmd.duration == 45

    def test_init_non_windows_warns(self) -> None:
        with patch("outlookctl.commands.create_timeblock.create_timeblock.os.name", "posix"), patch(
            "outlookctl.commands.create_timeblock.create_timeblock.console.warning"
        ) as warning_mock:
            CommandCreateTimeblock(duration=30)

        warning_mock.assert_called_once_with("OutlookLocalAdapter only available on Windows")

    def test_init_non_windows_outlook_is_none(self) -> None:
        with patch("outlookctl.commands.create_timeblock.create_timeblock.os.name", "posix"), patch(
            "outlookctl.commands.create_timeblock.create_timeblock.console.warning"
        ):
            cmd = CommandCreateTimeblock(duration=15)

        assert cmd.outlook is None


class TestCommandCreateTimeblockExecute:
    def test_execute_prints_message(self) -> None:
        with patch("outlookctl.commands.create_timeblock.create_timeblock.os.name", "posix"), patch(
            "outlookctl.commands.create_timeblock.create_timeblock.console.warning"
        ), patch("outlookctl.commands.create_timeblock.create_timeblock.console.print") as print_mock:
            cmd = CommandCreateTimeblock(duration=60)
            cmd.execute()

        print_mock.assert_called_once_with("Would create a timeblock of 60 minutes", mode="raw")
