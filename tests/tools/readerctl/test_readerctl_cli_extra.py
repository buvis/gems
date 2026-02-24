from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult, FatalError
from readerctl.cli import cli


class TestReaderctlLoginExtra:
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_login_success_no_output(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["login"])
        assert result.exit_code == 0

    @patch("readerctl.commands.login.login.CommandLogin")
    def test_login_failure_no_error(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        result = runner.invoke(cli, ["login"])
        assert result.exit_code == 0

    @patch("readerctl.commands.login.login.CommandLogin")
    def test_login_fatal_error(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.side_effect = FatalError("token file missing")
        result = runner.invoke(cli, ["login"])
        assert "token file missing" in result.output

    def test_login_import_error(self, runner) -> None:
        mod_key = "readerctl.commands.login.login"
        saved = sys.modules.pop(mod_key, None)
        try:
            with patch.dict(sys.modules, {mod_key: None}):
                result = runner.invoke(cli, ["login"])
                assert "readerctl" in result.output
        finally:
            if saved is not None:
                sys.modules[mod_key] = saved


class TestReaderctlAddExtra:
    @patch("readerctl.commands.add.add.CommandAdd")
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_add_url_failure(self, mock_login_cls: MagicMock, mock_add_cls: MagicMock, runner) -> None:
        mock_login_cls.return_value.execute.return_value = CommandResult(
            success=True, output="ok", metadata={"token": "tok"}
        )
        mock_add_cls.return_value.execute.return_value = CommandResult(success=False, error="bad url")
        result = runner.invoke(cli, ["add", "--url", "https://example.com"])
        assert result.exit_code == 0

    @patch("readerctl.commands.add.add.CommandAdd")
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_add_login_failure(self, mock_login_cls: MagicMock, mock_add_cls: MagicMock, runner) -> None:
        mock_login_cls.return_value.execute.return_value = CommandResult(success=False, error="bad token")
        result = runner.invoke(cli, ["add", "--url", "https://example.com"])
        assert result.exit_code != 0 or "Not logged in" in result.output

    @patch("readerctl.commands.add.add.CommandAdd")
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_add_login_fatal_error(self, mock_login_cls: MagicMock, mock_add_cls: MagicMock, runner) -> None:
        mock_login_cls.return_value.execute.side_effect = FatalError("broken")
        result = runner.invoke(cli, ["add", "--url", "https://example.com"])
        assert "broken" in result.output

    @patch("readerctl.commands.add.add.CommandAdd")
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_add_from_file(self, mock_login_cls: MagicMock, mock_add_cls: MagicMock, runner, tmp_path) -> None:
        mock_login_cls.return_value.execute.return_value = CommandResult(
            success=True, output="ok", metadata={"token": "tok"}
        )
        mock_add_cls.return_value.execute.return_value = CommandResult(success=True, output="Added")
        url_file = tmp_path / "urls.txt"
        url_file.write_text("https://a.com\nhttps://b.com\n")
        result = runner.invoke(cli, ["add", "--file", str(url_file)])
        assert result.exit_code == 0

    @patch("readerctl.commands.add.add.CommandAdd")
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_add_from_file_failure(self, mock_login_cls: MagicMock, mock_add_cls: MagicMock, runner, tmp_path) -> None:
        mock_login_cls.return_value.execute.return_value = CommandResult(
            success=True, output="ok", metadata={"token": "tok"}
        )
        mock_add_cls.return_value.execute.return_value = CommandResult(success=False, error="fail")
        url_file = tmp_path / "urls.txt"
        url_file.write_text("https://a.com\n")
        result = runner.invoke(cli, ["add", "--file", str(url_file)])
        assert result.exit_code == 0

    @patch("readerctl.commands.add.add.CommandAdd")
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_add_from_file_not_found(self, mock_login_cls: MagicMock, mock_add_cls: MagicMock, runner) -> None:
        mock_login_cls.return_value.execute.return_value = CommandResult(
            success=True, output="ok", metadata={"token": "tok"}
        )
        result = runner.invoke(cli, ["add", "--file", "/nonexistent/urls.txt"])
        assert "not found" in result.output

    @patch("readerctl.commands.add.add.CommandAdd")
    @patch("readerctl.commands.login.login.CommandLogin")
    def test_add_no_url_no_file(self, mock_login_cls: MagicMock, mock_add_cls: MagicMock, runner) -> None:
        result = runner.invoke(cli, ["add"])
        assert "Not logged in" in result.output

    def test_add_import_error(self, runner) -> None:
        mod_key = "readerctl.commands.add.add"
        saved = sys.modules.pop(mod_key, None)
        try:
            with patch.dict(sys.modules, {mod_key: None}):
                result = runner.invoke(cli, ["add", "--url", "https://x.com"])
                assert "readerctl" in result.output
        finally:
            if saved is not None:
                sys.modules[mod_key] = saved
