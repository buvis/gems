from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dot.commands.status.status import CommandStatus, get_git_modified_files


@pytest.fixture
def dotfiles_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "dotfiles"
    root.mkdir()
    monkeypatch.setenv("DOTFILES_ROOT", str(root))
    return root


class TestCommandStatusInit:
    def test_preserves_existing_dotfiles_root(self, tmp_path, monkeypatch) -> None:
        custom_root = tmp_path / "custom"
        custom_root.mkdir()
        monkeypatch.setenv("DOTFILES_ROOT", str(custom_root))
        shell = MagicMock()

        CommandStatus(shell=shell)

        import os

        assert os.environ["DOTFILES_ROOT"] == str(custom_root)


class TestCommandStatusExecute:
    def test_git_secret_hide_success(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", ""),  # cfg secret hide -m
            ("", "nothing to commit, working tree clean"),  # cfg status
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "No modifications found"
        assert shell.exe.call_count == 2
        shell.exe.assert_any_call("cfg secret hide -m", dotfiles_root)

    def test_git_secret_hide_error(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("secret error", "details")

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert "Error revealing secrets" in result.error

    def test_cfg_status_error(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("git error", "")

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert "Error executing command" in result.error

    def test_nothing_to_commit(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "On branch master\nnothing to commit, working tree clean")

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "No modifications found"
        assert result.warnings == []

    def test_unexpected_git_output(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "On branch master\nsome unexpected output")

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error == "Unexpected git output"
        assert result.metadata["details"] == "On branch master\nsome unexpected output"

    def test_empty_output(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "No modifications found"

    def test_modified_files_reported(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "modified: .bashrc\nmodified: .vimrc")

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.warnings) == 2
        assert any(".bashrc was modified" in w for w in result.warnings)
        assert any(".vimrc was modified" in w for w in result.warnings)


class TestGetGitModifiedFiles:
    def test_no_modified_lines(self) -> None:
        output = "On branch master\nnothing to commit\n"

        result = get_git_modified_files(output, Path("/tmp"))

        assert result == []

    def test_empty_output(self) -> None:
        result = get_git_modified_files("", Path("/tmp"))

        assert result == []

    def test_mixed_lines(self, tmp_path) -> None:
        output = "new file: readme.md\nmodified: config.yaml\ndeleted: old.txt\n"

        result = get_git_modified_files(output, tmp_path)

        assert len(result) == 1
        assert result[0] == (tmp_path / "config.yaml").resolve()
