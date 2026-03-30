from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from dot.commands.rm.rm import CommandRm


class TestCommandRmIsEncrypted:
    def test_returns_true_when_file_in_secret_list(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", ".secret_file\n.other_file")
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        assert cmd._is_encrypted()

    def test_returns_false_when_file_not_in_secret_list(
        self, dotfiles_root: Path
    ) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", ".other_file\n.another_file")
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        assert not cmd._is_encrypted()

    def test_returns_false_when_secret_list_errors(
        self, dotfiles_root: Path
    ) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("git-secret: abort", "")
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        assert not cmd._is_encrypted()


class TestCommandRmRemoveNormal:
    def test_removes_file_successfully(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "")
        cmd = CommandRm(shell=shell, file_path=".config/app.conf")
        result = cmd._remove_normal()
        assert result.success
        shell.exe.assert_called_once_with(
            "cfg rm .config/app.conf", dotfiles_root
        )

    def test_fails_on_cfg_rm_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("fatal: pathspec did not match", "")
        cmd = CommandRm(shell=shell, file_path=".config/app.conf")
        result = cmd._remove_normal()
        assert not result.success
        assert result.error


class TestCommandRmRemoveEncrypted:
    def test_removes_encrypted_file_fully(self, dotfiles_root: Path) -> None:
        gitignore = dotfiles_root / ".gitignore"
        gitignore.write_text(".secret_file\n.other_file\n")
        plaintext = dotfiles_root / ".secret_file"
        plaintext.write_text("secret content")

        shell = MagicMock()
        shell.exe.return_value = ("", "")
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        result = cmd._remove_encrypted()

        assert result.success
        shell.exe.assert_any_call(
            "cfg secret remove -c .secret_file", dotfiles_root
        )
        assert ".secret_file" not in gitignore.read_text()
        assert ".other_file" in gitignore.read_text()
        assert not plaintext.exists()

    def test_fails_on_secret_remove_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("git-secret: abort", "")
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        result = cmd._remove_encrypted()
        assert not result.success
        assert result.error

    def test_fails_on_gitignore_missing(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "")
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        result = cmd._remove_encrypted()
        assert result.success

    def test_cleans_only_matching_gitignore_line(
        self, dotfiles_root: Path
    ) -> None:
        gitignore = dotfiles_root / ".gitignore"
        gitignore.write_text(".secret_file\n.secret_file_backup\n.other\n")

        shell = MagicMock()
        shell.exe.return_value = ("", "")
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        cmd._remove_encrypted()

        lines = gitignore.read_text().splitlines()
        assert ".secret_file" not in lines
        assert ".secret_file_backup" in lines
        assert ".other" in lines


class TestCommandRmExecute:
    def test_dispatches_to_encrypted_path(self, dotfiles_root: Path) -> None:
        gitignore = dotfiles_root / ".gitignore"
        gitignore.write_text(".secret_file\n")
        plaintext = dotfiles_root / ".secret_file"
        plaintext.write_text("secret")

        shell = MagicMock()
        # _is_encrypted call returns file in list, then _remove_encrypted succeeds
        shell.exe.side_effect = [
            ("", ".secret_file"),  # cfg secret list
            ("", ""),              # cfg secret remove -c
        ]
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        result = cmd.execute()

        assert result.success
        shell.exe.assert_any_call(
            "cfg secret remove -c .secret_file", dotfiles_root
        )

    def test_dispatches_to_normal_path(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        # _is_encrypted returns empty list, then _remove_normal succeeds
        shell.exe.side_effect = [
            ("", ""),   # cfg secret list (empty)
            ("", ""),   # cfg rm
        ]
        cmd = CommandRm(shell=shell, file_path=".config/app.conf")
        result = cmd.execute()

        assert result.success
        shell.exe.assert_any_call(
            "cfg rm .config/app.conf", dotfiles_root
        )
