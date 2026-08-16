from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from dot.commands.rm.rm import CommandRm


class TestCommandRmInit:
    @patch("dot.commands.rm.rm.DotGitService")
    def test_constructs_dot_git_service_with_shell_and_dotfiles_root(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandRm(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".bashrc")

        mock_service_cls.assert_called_once_with(shell, str(dotfiles_root))

    def test_does_not_mutate_environment(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()

        with patch("dot.commands.rm.rm.DotGitService"):
            CommandRm(shell=shell, dotfiles_root=str(tmp_path), file_path=".bashrc")

        assert "DOTFILES_ROOT" not in os.environ

    @patch("dot.commands.rm.rm.DotGitService")
    def test_does_not_call_shell_alias(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandRm(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".bashrc")

        shell.alias.assert_not_called()


class TestCommandRmExecute:
    @patch("dot.commands.rm.rm.DotGitService")
    def test_execute_removes_via_service_with_file_path_and_returns_success(
        self, mock_service_cls, dotfiles_root
    ) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.rm.return_value = CommandResult(success=True, output=".bashrc removed from tracking", warnings=[])
        shell = MagicMock()

        cmd = CommandRm(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".bashrc")
        result = cmd.execute()

        mock_service.rm.assert_called_once_with(".bashrc")
        assert result.success
        assert result.output == ".bashrc removed from tracking"
        assert result.warnings == []

    @patch("dot.commands.rm.rm.DotGitService")
    def test_execute_returns_service_failure_passthrough(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.rm.return_value = CommandResult(success=False, error="Failed to remove: fatal error")
        shell = MagicMock()

        cmd = CommandRm(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".bashrc")
        result = cmd.execute()

        assert not result.success
        assert result.error == "Failed to remove: fatal error"

    @patch("dot.commands.rm.rm.DotGitService")
    def test_execute_calls_service_rm_exactly_once(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.rm.return_value = CommandResult(success=True, output="ok", warnings=[])
        shell = MagicMock()

        cmd = CommandRm(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".bashrc")
        cmd.execute()

        assert mock_service.rm.call_count == 1

    @patch("dot.commands.rm.rm.DotGitService")
    def test_execute_never_calls_shell_directly(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.rm.return_value = CommandResult(success=True, output=".bashrc removed from tracking", warnings=[])
        shell = MagicMock()

        cmd = CommandRm(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".bashrc")
        cmd.execute()

        shell.exe.assert_not_called()
        shell.interact.assert_not_called()
        shell.alias.assert_not_called()
