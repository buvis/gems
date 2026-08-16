from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from dot.commands.encrypt.encrypt import CommandEncrypt


class TestCommandEncryptInit:
    @patch("dot.commands.encrypt.encrypt.DotGitService")
    def test_constructs_dot_git_service_with_shell_and_dotfiles_root(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        cmd = CommandEncrypt(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".secret_file")

        mock_service_cls.assert_called_once_with(shell, str(dotfiles_root))
        assert cmd.file_path == ".secret_file"

    def test_does_not_mutate_environment(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()

        with patch("dot.commands.encrypt.encrypt.DotGitService"):
            CommandEncrypt(shell=shell, dotfiles_root=str(tmp_path), file_path=".secret_file")

        assert "DOTFILES_ROOT" not in os.environ

    @patch("dot.commands.encrypt.encrypt.DotGitService")
    def test_does_not_call_shell_alias(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandEncrypt(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".secret_file")

        shell.alias.assert_not_called()


class TestCommandEncryptExecuteWithoutGitSecret:
    @patch("dot.commands.encrypt.encrypt.DotGitService")
    def test_execute_fails_without_calling_encrypt_and_stage(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.is_secret_tool_available.return_value = False
        shell = MagicMock()

        cmd = CommandEncrypt(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".secret_file")
        result = cmd.execute()

        assert not result.success
        assert result.error == "git-secret is not installed"
        mock_service.encrypt_and_stage.assert_not_called()

    @patch("dot.commands.encrypt.encrypt.DotGitService")
    def test_execute_never_calls_shell_directly(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.is_secret_tool_available.return_value = False
        shell = MagicMock()

        cmd = CommandEncrypt(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".secret_file")
        cmd.execute()

        shell.exe.assert_not_called()
        shell.interact.assert_not_called()
        shell.alias.assert_not_called()
        shell.is_command_available.assert_not_called()


class TestCommandEncryptExecuteWithGitSecret:
    @patch("dot.commands.encrypt.encrypt.DotGitService")
    def test_execute_encrypts_via_service_with_file_path_and_returns_success(
        self, mock_service_cls, dotfiles_root
    ) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.is_secret_tool_available.return_value = True
        mock_service.encrypt_and_stage.return_value = CommandResult(
            success=True, output=".secret_file encrypted and staged"
        )
        shell = MagicMock()

        cmd = CommandEncrypt(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".secret_file")
        result = cmd.execute()

        mock_service.encrypt_and_stage.assert_called_once_with(".secret_file")
        assert result.success
        assert result.output == ".secret_file encrypted and staged"

    @patch("dot.commands.encrypt.encrypt.DotGitService")
    def test_execute_returns_service_failure_passthrough(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.is_secret_tool_available.return_value = True
        mock_service.encrypt_and_stage.return_value = CommandResult(
            success=False, error="Failed to encrypt: hide error"
        )
        shell = MagicMock()

        cmd = CommandEncrypt(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".secret_file")
        result = cmd.execute()

        assert not result.success
        assert result.error == "Failed to encrypt: hide error"

    @patch("dot.commands.encrypt.encrypt.DotGitService")
    def test_execute_calls_service_encrypt_and_stage_exactly_once(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.is_secret_tool_available.return_value = True
        mock_service.encrypt_and_stage.return_value = CommandResult(success=True, output="ok")
        shell = MagicMock()

        cmd = CommandEncrypt(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".secret_file")
        cmd.execute()

        assert mock_service.encrypt_and_stage.call_count == 1

    @patch("dot.commands.encrypt.encrypt.DotGitService")
    def test_execute_never_calls_shell_directly(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.is_secret_tool_available.return_value = True
        mock_service.encrypt_and_stage.return_value = CommandResult(
            success=True, output=".secret_file encrypted and staged"
        )
        shell = MagicMock()

        cmd = CommandEncrypt(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".secret_file")
        cmd.execute()

        shell.exe.assert_not_called()
        shell.interact.assert_not_called()
        shell.alias.assert_not_called()
        shell.is_command_available.assert_not_called()
