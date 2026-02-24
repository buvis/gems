from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from dot.commands.encrypt.encrypt import CommandEncrypt


class TestCommandEncryptInit:
    def test_init_sets_env_and_alias(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.encrypt.encrypt.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandEncrypt(shell=shell, file_path=".secret_file")

        import os

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.file_path == ".secret_file"


class TestCommandEncryptExecute:
    def test_fails_without_git_secret(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False

        cmd = CommandEncrypt(shell=shell, file_path=".secret_file")
        result = cmd.execute()

        assert not result.success
        assert "git-secret is not installed" in result.error

    def test_registers_encrypts_and_stages(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [("", ""), ("", ""), ("", "")]

        cmd = CommandEncrypt(shell=shell, file_path=".secret_file")
        result = cmd.execute()

        assert result.success
        assert "encrypted and staged" in result.output
        assert shell.exe.call_count == 3
        shell.exe.assert_any_call("cfg secret add .secret_file", dotfiles_root)
        shell.exe.assert_any_call("cfg secret hide -m", dotfiles_root)
        shell.exe.assert_any_call("cfg add .secret_file.secret .gitsecret/", dotfiles_root)

    def test_fails_on_secret_add_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("add error", "")

        cmd = CommandEncrypt(shell=shell, file_path=".secret_file")
        result = cmd.execute()

        assert not result.success
        assert "Failed to register file" in result.error

    def test_fails_on_hide_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [("", ""), ("hide error", "")]

        cmd = CommandEncrypt(shell=shell, file_path=".secret_file")
        result = cmd.execute()

        assert not result.success
        assert "Failed to encrypt" in result.error

    def test_fails_on_stage_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [("", ""), ("", ""), ("stage error", "")]

        cmd = CommandEncrypt(shell=shell, file_path=".secret_file")
        result = cmd.execute()

        assert not result.success
        assert "Failed to stage" in result.error
