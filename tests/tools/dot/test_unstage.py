from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from dot.commands.unstage.unstage import CommandUnstage


class TestCommandUnstageInit:
    @patch("dot.commands.unstage.unstage.DotGitService")
    def test_constructs_dot_git_service_with_shell_and_dotfiles_root(
        self, mock_service_cls, dotfiles_root: Path
    ) -> None:
        shell = MagicMock()

        CommandUnstage(shell=shell, dotfiles_root=str(dotfiles_root))

        mock_service_cls.assert_called_once_with(shell, str(dotfiles_root))

    def test_does_not_mutate_environment(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()

        with patch("dot.commands.unstage.unstage.DotGitService"):
            CommandUnstage(shell=shell, dotfiles_root=str(tmp_path))

        assert "DOTFILES_ROOT" not in os.environ

    @patch("dot.commands.unstage.unstage.DotGitService")
    def test_does_not_call_shell_alias(self, mock_service_cls, dotfiles_root: Path) -> None:
        shell = MagicMock()

        CommandUnstage(shell=shell, dotfiles_root=str(dotfiles_root))

        shell.alias.assert_not_called()

    @patch("dot.commands.unstage.unstage.DotGitService")
    def test_stores_shell(self, mock_service_cls, dotfiles_root: Path) -> None:
        shell = MagicMock()

        cmd = CommandUnstage(shell=shell, dotfiles_root=str(dotfiles_root))

        assert cmd.shell is shell


class TestCommandUnstageExecute:
    @patch("dot.commands.unstage.unstage.DotGitService")
    def test_unstage_all_calls_service_with_none(self, mock_service_cls, dotfiles_root: Path) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.unstage.return_value = CommandResult(success=True, output="All files unstaged")
        shell = MagicMock()

        cmd = CommandUnstage(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        mock_service.unstage.assert_called_once_with(None)
        assert result.success
        assert result.output == "All files unstaged"

    @patch("dot.commands.unstage.unstage.DotGitService")
    def test_unstage_specific_file_calls_service_with_path(self, mock_service_cls, dotfiles_root: Path) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.unstage.return_value = CommandResult(success=True, output=".bashrc unstaged")
        shell = MagicMock()

        cmd = CommandUnstage(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".bashrc")
        result = cmd.execute()

        mock_service.unstage.assert_called_once_with(".bashrc")
        assert result.success
        assert result.output == ".bashrc unstaged"

    @patch("dot.commands.unstage.unstage.DotGitService")
    def test_execute_returns_service_error_result_unchanged(self, mock_service_cls, dotfiles_root: Path) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.unstage.return_value = CommandResult(success=False, error="Unstage failed: reset error")
        shell = MagicMock()

        cmd = CommandUnstage(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert not result.success
        assert result.error == "Unstage failed: reset error"

    @patch("dot.commands.unstage.unstage.DotGitService")
    def test_execute_is_a_passthrough_of_the_service_result(self, mock_service_cls, dotfiles_root: Path) -> None:
        mock_service = mock_service_cls.return_value
        service_result = CommandResult(success=True, output="All files unstaged")
        mock_service.unstage.return_value = service_result
        shell = MagicMock()

        cmd = CommandUnstage(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result is service_result

    @patch("dot.commands.unstage.unstage.DotGitService")
    def test_execute_never_calls_shell_directly(self, mock_service_cls, dotfiles_root: Path) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.unstage.return_value = CommandResult(success=True, output="All files unstaged")
        shell = MagicMock()

        cmd = CommandUnstage(shell=shell, dotfiles_root=str(dotfiles_root))
        cmd.execute()

        shell.exe.assert_not_called()
        shell.interact.assert_not_called()
        shell.alias.assert_not_called()
