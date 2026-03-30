from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from dot.commands.delete.delete import CommandDelete


class TestCommandDeleteNormal:
    def test_deletes_file_from_tracking_and_disk(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.side_effect = [
            ("", ""),  # cfg secret list (not encrypted)
            ("", ""),  # cfg rm
        ]
        cmd = CommandDelete(shell=shell, file_path=".config/app.conf")
        result = cmd.execute()
        assert result.success
        shell.exe.assert_any_call(
            "cfg rm .config/app.conf", dotfiles_root
        )

    def test_fails_on_cfg_rm_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.side_effect = [
            ("", ""),  # cfg secret list
            ("fatal: pathspec did not match", ""),  # cfg rm error
        ]
        cmd = CommandDelete(shell=shell, file_path=".config/app.conf")
        result = cmd.execute()
        assert not result.success


class TestCommandDeleteEncrypted:
    def test_deletes_encrypted_file_fully(self, dotfiles_root: Path) -> None:
        gitignore = dotfiles_root / ".gitignore"
        gitignore.write_text(".secret_file\n.other_file\n")
        plaintext = dotfiles_root / ".secret_file"
        plaintext.write_text("secret content")

        shell = MagicMock()
        shell.exe.side_effect = [
            ("", ".secret_file"),  # cfg secret list
            ("", ""),              # cfg secret remove -c
            ("", ""),              # cfg add .gitignore
        ]
        cmd = CommandDelete(shell=shell, file_path=".secret_file")
        result = cmd.execute()

        assert result.success
        shell.exe.assert_any_call(
            "cfg secret remove -c .secret_file", dotfiles_root
        )
        assert not plaintext.exists()

    def test_fails_on_secret_remove_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.side_effect = [
            ("", ".secret_file"),  # cfg secret list
            ("git-secret: abort", ""),  # cfg secret remove error
        ]
        cmd = CommandDelete(shell=shell, file_path=".secret_file")
        result = cmd.execute()
        assert not result.success
