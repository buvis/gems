from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dot.commands.add.add import CommandAdd
from dot.commands.commit.commit import CommandCommit
from dot.commands.pull.pull import CommandPull
from dot.commands.push.push import CommandPush
from dot.commands.status.status import CommandStatus, get_git_modified_files


@pytest.fixture
def dotfiles_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "dotfiles"
    root.mkdir()
    monkeypatch.setenv("DOTFILES_ROOT", str(root))
    return root


class TestCommandStatusInit:
    def test_init_sets_env_and_alias(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.status.status.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandStatus(shell=shell)

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell


class TestCommandStatusExecute:
    def test_execute_calls_status_and_reports_modified_files(self, dotfiles_root):
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = (
            "",
            "modified: foo.txt\nmodified: dir/bar.txt\n",
        )

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        shell.exe.assert_called_once_with("cfg status", dotfiles_root)

        assert result.success
        expected = [
            (Path.cwd() / "foo.txt").resolve(),
            (Path.cwd() / "dir/bar.txt").resolve(),
        ]
        assert f"{expected[0]} was modified" in result.warnings
        assert f"{expected[1]} was modified" in result.warnings
        assert len(result.warnings) == 2


class TestGetGitModifiedFiles:
    def test_parses_modified_lines(self, tmp_path):
        output = "modified: path/to/file.txt\n  modified: other.txt\nnew file: x\n"

        result = get_git_modified_files(output, tmp_path)

        assert result == [
            (tmp_path / "path/to/file.txt").resolve(),
            (tmp_path / "other.txt").resolve(),
        ]


class TestCommandAddInit:
    def test_init_sets_env_and_alias(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.add.add.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandAdd(shell=shell)

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell


class TestCommandAddExecute:
    def test_execute_uses_patch_for_tracked_file(self, dotfiles_root, tmp_path):
        shell = MagicMock()
        file_path = tmp_path / "tracked.txt"
        file_path.write_text("data")
        shell.exe.return_value = ("", "")

        cmd = CommandAdd(shell=shell, file_path=str(file_path))
        result = cmd.execute()

        shell.exe.assert_called_once_with(
            f"cfg ls-files --error-unmatch {file_path}",
            dotfiles_root,
        )
        shell.interact.assert_called_once_with(
            f"cfg add -p {file_path}",
            "Stage this hunk [y,n,q,a,d,j,J,g,/,e,?]?",
            dotfiles_root,
        )
        assert result.success

    def test_execute_uses_add_for_untracked_file(self, dotfiles_root, tmp_path):
        shell = MagicMock()
        file_path = tmp_path / "untracked.txt"
        file_path.write_text("data")
        shell.exe.return_value = ("returned non-zero exit status 1", "")

        cmd = CommandAdd(shell=shell, file_path=str(file_path))
        result = cmd.execute()

        shell.exe.assert_called_once_with(
            f"cfg ls-files --error-unmatch {file_path}",
            dotfiles_root,
        )
        shell.interact.assert_called_once_with(
            f"cfg add {file_path}",
            "Stage this hunk [y,n,q,a,d,j,J,g,/,e,?]?",
            dotfiles_root,
        )
        assert result.success


class TestCommandPullInit:
    def test_init_sets_env_and_alias(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.pull.pull.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandPull(shell=shell)

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell


class TestCommandPullExecute:
    def test_execute_pulls_and_updates_submodules(self, dotfiles_root):
        shell = MagicMock()
        shell.exe.side_effect = [("", ""), ("", ""), ("", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "Dotfiles pulled successfully"
        assert shell.exe.call_count == 3
        shell.exe.assert_any_call("cfg pull", dotfiles_root)
        shell.exe.assert_any_call("cfg submodule update --init", dotfiles_root)
        shell.exe.assert_any_call("cfg submodule update --remote --merge", dotfiles_root)

    def test_execute_fails_on_pull_error(self, dotfiles_root):
        shell = MagicMock()
        shell.exe.side_effect = [("error msg", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Pull failed")

    def test_execute_fails_on_submodule_init_error(self, dotfiles_root):
        shell = MagicMock()
        shell.exe.side_effect = [("", ""), ("error msg", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Submodule init failed")

    def test_execute_fails_on_submodule_update_error(self, dotfiles_root):
        shell = MagicMock()
        shell.exe.side_effect = [("", ""), ("", ""), ("error msg", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Submodule update failed")


class TestCommandCommitInit:
    def test_init_sets_env_and_alias(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.commit.commit.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandCommit(shell=shell, message="message")

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell
        assert cmd.message == "message"


class TestCommandCommitExecute:
    def test_execute_commits_without_git_secret(self, dotfiles_root):
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        cmd = CommandCommit(shell=shell, message="message")
        result = cmd.execute()

        assert result.success
        assert result.output == "Changes committed"
        assert result.warnings == []

    def test_execute_commits_with_git_secret_success(self, dotfiles_root):
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [("", ""), ("", "")]

        cmd = CommandCommit(shell=shell, message="message")
        result = cmd.execute()

        assert result.success
        assert result.warnings == []
        assert shell.exe.call_count == 2
        shell.exe.assert_any_call("cfg secret hide -m", dotfiles_root)

    def test_execute_fails_on_git_secret_failure(self, dotfiles_root):
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [("secret err", "details")]

        cmd = CommandCommit(shell=shell, message="message")
        result = cmd.execute()

        assert not result.success
        assert "Error hiding secrets" in result.error

    def test_execute_fails_on_commit_error(self, dotfiles_root):
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("commit error", "")

        cmd = CommandCommit(shell=shell, message="message")
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Commit failed")

    def test_execute_quotes_message(self, dotfiles_root):
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        cmd = CommandCommit(shell=shell, message="hello world")
        result = cmd.execute()

        assert result.success
        command = shell.exe.call_args.args[0]
        assert "'hello world'" in command


class TestCommandPushInit:
    def test_init_sets_env_and_alias(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.push.push.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandPush(shell=shell)

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell


class TestCommandPushExecute:
    def test_execute_pushes_successfully(self, dotfiles_root):
        shell = MagicMock()
        shell.exe.return_value = ("", "")

        cmd = CommandPush(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "Changes pushed"

    def test_execute_fails_on_push_error(self, dotfiles_root):
        shell = MagicMock()
        shell.exe.return_value = ("push error", "")

        cmd = CommandPush(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Push failed")
