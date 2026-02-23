from __future__ import annotations

import sys
from unittest.mock import patch

from buvis.pybase.result import CommandResult
from pinger.cli import cli


class TestPingerCommands:
    def test_wait_success(self, mocker, runner) -> None:
        mock_cmd_cls = mocker.patch("pinger.commands.wait.wait.CommandWait")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="ok")
        result = runner.invoke(cli, ["wait", "192.168.1.1"])
        assert result.exit_code == 0
        assert "online" in result.output

    def test_wait_with_timeout(self, mocker, runner) -> None:
        mock_cmd_cls = mocker.patch("pinger.commands.wait.wait.CommandWait")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="ok")
        result = runner.invoke(cli, ["wait", "-t", "10", "example.com"])
        assert result.exit_code == 0

    def test_wait_timeout(self, mocker, runner) -> None:
        mocker.patch("pinger.commands.wait.exceptions.CommandWaitTimeoutError", Exception)
        mock_cmd_cls = mocker.patch("pinger.commands.wait.wait.CommandWait")
        from pinger.commands.wait.exceptions import CommandWaitTimeoutError

        mock_cmd_cls.return_value.execute.side_effect = CommandWaitTimeoutError
        result = runner.invoke(cli, ["wait", "10.0.0.1"])
        assert result.exit_code != 0 or "Timeout" in result.output


class TestPingerImportError:
    def test_wait_import_error(self, runner) -> None:
        mod_key = "pinger.commands.wait.wait"
        saved = sys.modules.pop(mod_key, None)
        try:
            with patch.dict(sys.modules, {mod_key: None}):
                result = runner.invoke(cli, ["wait", "10.0.0.1"])
                assert "pinger" in result.output
        finally:
            if saved is not None:
                sys.modules[mod_key] = saved
