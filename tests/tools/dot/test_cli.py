from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from dot.commands.add import add as add_module
from dot.commands.status import status as status_module


@pytest.fixture
def dotfiles_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "dotfiles"
    root.mkdir()
    monkeypatch.setenv("DOTFILES_ROOT", str(root))
    return root


@pytest.fixture
def status_shell(monkeypatch) -> tuple[MagicMock, MagicMock]:
    shell = MagicMock()
    shell.is_command_available.return_value = False
    shell_adapter = MagicMock(return_value=shell)
    monkeypatch.setattr(status_module, "ShellAdapter", shell_adapter)
    return shell_adapter, shell


@pytest.fixture
def add_shell(monkeypatch) -> tuple[MagicMock, MagicMock]:
    shell = MagicMock()
    shell_adapter = MagicMock(return_value=shell)
    monkeypatch.setattr(add_module, "ShellAdapter", shell_adapter)
    return shell_adapter, shell


class TestCommandStatusInit:
    def test_init_sets_env_and_alias(self, status_shell, tmp_path, monkeypatch):
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr(status_module.Path, "home", lambda: tmp_path)
        shell_adapter, shell = status_shell

        cmd = status_module.CommandStatus()

        shell_adapter.assert_called_once_with(suppress_logging=True)
        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell


class TestCommandStatusExecute:
    def test_execute_calls_status_and_logs_modified_files(self, status_shell, dotfiles_root):
        shell_adapter, shell = status_shell
        shell.is_command_available.return_value = False
        shell.exe.return_value = (
            "",
            "modified: foo.txt\nmodified: dir/bar.txt\n",
        )

        with patch.object(status_module.console, "warning") as warning_mock:
            cmd = status_module.CommandStatus()
            cmd.execute()

        shell_adapter.assert_called_once_with(suppress_logging=True)
        shell.exe.assert_called_once_with("cfg status", str(dotfiles_root))

        expected = [
            (Path.cwd() / "foo.txt").resolve(),
            (Path.cwd() / "dir/bar.txt").resolve(),
        ]
        warning_mock.assert_has_calls([call(f"{expected[0]} was modified"), call(f"{expected[1]} was modified")])
        assert warning_mock.call_count == 2


class TestGetGitModifiedFiles:
    def test_parses_modified_lines(self, tmp_path):
        output = "modified: path/to/file.txt\n  modified: other.txt\nnew file: x\n"

        result = status_module.get_git_modified_files(output, tmp_path)

        assert result == [
            (tmp_path / "path/to/file.txt").resolve(),
            (tmp_path / "other.txt").resolve(),
        ]


class TestCommandAddInit:
    def test_init_sets_env_and_alias(self, add_shell, tmp_path, monkeypatch):
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr(add_module.Path, "home", lambda: tmp_path)
        shell_adapter, shell = add_shell

        cmd = add_module.CommandAdd()

        shell_adapter.assert_called_once_with(suppress_logging=True)
        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell


class TestCommandAddExecute:
    def test_execute_uses_patch_for_tracked_file(self, add_shell, dotfiles_root, tmp_path):
        shell_adapter, shell = add_shell
        file_path = tmp_path / "tracked.txt"
        file_path.write_text("data")
        shell.exe.return_value = ("", "")

        cmd = add_module.CommandAdd(file_path=str(file_path))
        cmd.execute()

        shell_adapter.assert_called_once_with(suppress_logging=True)
        shell.exe.assert_called_once_with(
            f"cfg ls-files --error-unmatch {file_path}",
            str(dotfiles_root),
        )
        shell.interact.assert_called_once_with(
            f"cfg add -p {file_path}",
            "Stage this hunk [y,n,q,a,d,j,J,g,/,e,?]?",
            str(dotfiles_root),
        )

    def test_execute_uses_add_for_untracked_file(self, add_shell, dotfiles_root, tmp_path):
        shell_adapter, shell = add_shell
        file_path = tmp_path / "untracked.txt"
        file_path.write_text("data")
        shell.exe.return_value = ("returned non-zero exit status 1", "")

        cmd = add_module.CommandAdd(file_path=str(file_path))
        cmd.execute()

        shell_adapter.assert_called_once_with(suppress_logging=True)
        shell.exe.assert_called_once_with(
            f"cfg ls-files --error-unmatch {file_path}",
            str(dotfiles_root),
        )
        shell.interact.assert_called_once_with(
            f"cfg add {file_path}",
            "Stage this hunk [y,n,q,a,d,j,J,g,/,e,?]?",
            str(dotfiles_root),
        )
