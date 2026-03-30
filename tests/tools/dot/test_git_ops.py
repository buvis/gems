from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dot.tui.git_ops import GitOps
from dot.tui.models import BranchInfo, FileEntry


@pytest.fixture
def shell() -> MagicMock:
    mock = MagicMock()
    mock.exe.return_value = ("", "")
    return mock


@pytest.fixture
def git_ops(shell: MagicMock) -> GitOps:
    ops = GitOps(shell=shell, dotfiles_root="/home/user/dotfiles")
    shell.exe.reset_mock()
    return ops


class TestGitOpsStatus:
    def test_empty_output_returns_empty_list(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        result = git_ops.status()

        assert result == []

    def test_modified_staged(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "M  .bashrc")

        result = git_ops.status()

        assert FileEntry(path=".bashrc", status="M ") in result

    def test_modified_unstaged(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", " M .bashrc")

        result = git_ops.status()

        assert FileEntry(path=".bashrc", status=" M") in result

    def test_added_staged(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "A  .newrc")

        result = git_ops.status()

        assert FileEntry(path=".newrc", status="A ") in result

    def test_deleted_unstaged(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", " D .oldrc")

        result = git_ops.status()

        assert FileEntry(path=".oldrc", status=" D") in result

    def test_untracked(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "?? newfile.txt")

        result = git_ops.status()

        assert FileEntry(path="newfile.txt", status="??") in result

    def test_multiple_files(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "M  .bashrc\n M .vimrc\n?? new.txt")

        result = git_ops.status()

        assert len(result) == 3

    def test_both_staged_and_unstaged_same_file(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "MM .bashrc")

        result = git_ops.status()

        assert FileEntry(path=".bashrc", status="MM") in result

    def test_file_with_spaces_in_path(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "M  my config file.txt")

        result = git_ops.status()

        assert FileEntry(path="my config file.txt", status="M ") in result

    def test_secret_files_marked(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", "M  .bashrc\nM  .ssh/config"),  # cfg status --porcelain
            ("", ".ssh/config\n"),  # cfg secret list
        ]

        result = git_ops.status()

        bashrc = next(f for f in result if f.path == ".bashrc")
        ssh_config = next(f for f in result if f.path == ".ssh/config")
        assert bashrc.is_secret is False
        assert ssh_config.is_secret is True

    def test_git_secret_unavailable_all_not_secret(
        self, git_ops: GitOps, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "M  .bashrc\nM  .ssh/config")

        result = git_ops.status()

        assert all(not f.is_secret for f in result)

    def test_git_secret_list_error_all_not_secret(
        self, git_ops: GitOps, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", "M  .bashrc"),  # cfg status --porcelain
            ("error getting secrets", ""),  # cfg secret list fails
        ]

        result = git_ops.status()

        assert all(not f.is_secret for f in result)


class TestGitOpsDiff:
    def test_unstaged_diff(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "diff --git a/.bashrc b/.bashrc\n-old\n+new")

        result = git_ops.diff(".bashrc")

        shell.exe.assert_called_once()
        cmd = shell.exe.call_args[0][0]
        assert "cfg diff" in cmd
        assert "--cached" not in cmd
        assert ".bashrc" in cmd
        assert result == "diff --git a/.bashrc b/.bashrc\n-old\n+new"

    def test_staged_diff(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "diff --git a/.bashrc b/.bashrc\n-old\n+new")

        git_ops.diff(".bashrc", staged=True)

        cmd = shell.exe.call_args[0][0]
        assert "--cached" in cmd
        assert ".bashrc" in cmd

    def test_returns_output_text(self, git_ops: GitOps, shell: MagicMock) -> None:
        expected = "--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new"
        shell.exe.return_value = ("", expected)

        result = git_ops.diff("file")

        assert result == expected

    def test_returns_empty_on_no_diff(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_ops.diff("file")

        assert result == ""


class TestGitOpsStage:
    def test_success(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_ops.stage(".bashrc")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg add" in cmd
        assert ".bashrc" in cmd

    def test_failure(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("fatal: pathspec 'bad' did not match", "")

        result = git_ops.stage("bad")

        assert result.success is False
        assert result.error is not None


class TestGitOpsUnstage:
    def test_success(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_ops.unstage(".bashrc")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg reset HEAD --" in cmd
        assert ".bashrc" in cmd

    def test_failure(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("error: unstage failed", "")

        result = git_ops.unstage(".bashrc")

        assert result.success is False


class TestGitOpsCommit:
    def test_commit_without_git_secret(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "[master abc1234] my message")

        result = git_ops.commit("my message")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg commit -m" in cmd
        assert "my message" in cmd

    def test_commit_with_git_secret_hides_first(
        self, git_ops: GitOps, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", ""),  # cfg secret hide -m
            ("", "[master abc1234] my message"),  # cfg commit
        ]

        result = git_ops.commit("my message")

        assert result.success is True
        assert shell.exe.call_count == 2
        hide_cmd = shell.exe.call_args_list[0][0][0]
        assert "cfg secret hide -m" in hide_cmd
        commit_cmd = shell.exe.call_args_list[1][0][0]
        assert "cfg commit -m" in commit_cmd

    def test_commit_failure(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("nothing to commit", "")

        result = git_ops.commit("my message")

        assert result.success is False
        assert result.error is not None

    def test_commit_secret_hide_failure(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("secret hide error", "")

        result = git_ops.commit("my message")

        assert result.success is False


class TestGitOpsPush:
    def test_success_with_unpushed(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", "1\n"),  # rev-list count: 1 unpushed
            ("", "Everything up-to-date"),  # cfg push
        ]

        result = git_ops.push()

        assert result.success is True
        push_cmd = shell.exe.call_args_list[1][0][0]
        assert "cfg push" in push_cmd

    def test_nothing_to_push(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "0\n")  # rev-list count: 0 unpushed

        result = git_ops.push()

        assert result.success is True
        assert result.output == "Nothing to push"
        assert shell.exe.call_count == 1  # only the check, no push

    def test_failure(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", "1\n"),  # has unpushed
            ("rejected: non-fast-forward", ""),  # push fails
        ]

        result = git_ops.push()

        assert result.success is False


class TestGitOpsPull:
    def test_success_full_flow(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "ok")

        result = git_ops.pull()

        assert result.success is True
        assert shell.exe.call_count == 4  # pull + 3 submodule commands
        cmds = [c[0][0] for c in shell.exe.call_args_list]
        assert "cfg pull" in cmds[0]
        assert "submodule foreach" in cmds[1]
        assert "submodule update --init" in cmds[2]
        assert "submodule update --remote --merge" in cmds[3]

    def test_success_with_secret_reveal(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", "ok")

        result = git_ops.pull()

        assert result.success is True
        assert shell.exe.call_count == 5  # pull + 3 submodule + secret reveal
        last_cmd = shell.exe.call_args_list[4][0][0]
        assert "cfg secret reveal -f" in last_cmd

    def test_pull_failure(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("merge conflict", "")

        result = git_ops.pull()

        assert result.success is False

    def test_submodule_failure(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "ok"),  # pull ok
            ("submodule error", ""),  # submodule fails
        ]

        result = git_ops.pull()

        assert result.success is False
        assert "Submodule" in (result.error or "")


class TestGitOpsRm:
    def test_success(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "rm '.bashrc'")

        result = git_ops.rm(".bashrc")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg rm" in cmd
        assert ".bashrc" in cmd

    def test_failure(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("pathspec 'missing' did not match", "")

        result = git_ops.rm("missing")

        assert result.success is False


class TestGitOpsAddToGitignore:
    def test_appends_pattern(self, git_ops: GitOps, tmp_path: Path) -> None:
        git_ops._wd = tmp_path
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")
        shell = git_ops.shell
        shell.exe.return_value = ("", "")

        result = git_ops.add_to_gitignore("node_modules/")

        assert result.success is True
        assert "node_modules/" in gitignore.read_text()
        assert "*.pyc" in gitignore.read_text()

    def test_creates_gitignore_if_missing(self, git_ops: GitOps, tmp_path: Path) -> None:
        git_ops._wd = tmp_path
        shell = git_ops.shell
        shell.exe.return_value = ("", "")

        result = git_ops.add_to_gitignore("*.log")

        assert result.success is True
        assert (tmp_path / ".gitignore").read_text() == "*.log\n"

    def test_stages_gitignore_after_write(self, git_ops: GitOps, tmp_path: Path) -> None:
        git_ops._wd = tmp_path
        shell = git_ops.shell
        shell.exe.return_value = ("", "")

        git_ops.add_to_gitignore("tmp/")

        cmd = shell.exe.call_args[0][0]
        assert "cfg add" in cmd
        assert ".gitignore" in cmd


class TestGitOpsBranchInfo:
    def test_parses_branch_name(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "master\n"),  # rev-parse --abbrev-ref HEAD
            ("", "0\t0\n"),  # rev-list --count --left-right
        ]

        result = git_ops.branch_info()

        assert result.name == "master"

    def test_parses_ahead_behind(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "main\n"),  # rev-parse
            ("", "2\t3\n"),  # rev-list: 2 behind, 3 ahead
        ]

        result = git_ops.branch_info()

        assert result.ahead == 3
        assert result.behind == 2

    def test_parses_secret_count(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", "master\n"),  # rev-parse
            ("", "0\t0\n"),  # rev-list
            ("", ".ssh/config\n.gnupg/keys\n"),  # secret list
        ]

        result = git_ops.branch_info()

        assert result.secret_count == 2

    def test_no_git_secret_zero_secrets(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "master\n"),
            ("", "0\t0\n"),
        ]

        result = git_ops.branch_info()

        assert result.secret_count == 0

    def test_defaults_when_rev_parse_fails(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("fatal: not a git repo", ""),  # rev-parse fails
            ("fatal: no upstream", ""),  # rev-list @{u} fails
            ("fatal: no remote", ""),  # rev-list origin/unknown fails
        ]

        result = git_ops.branch_info()

        assert result.name == "unknown"
        assert result.ahead == 0
        assert result.behind == 0

    def test_defaults_when_rev_list_fails(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "master\n"),  # rev-parse ok
            ("fatal: no upstream", ""),  # rev-list @{u} fails
            ("fatal: no remote", ""),  # rev-list origin/master fails
        ]

        result = git_ops.branch_info()

        assert result.name == "master"
        assert result.ahead == 0
        assert result.behind == 0

    def test_secret_list_error_zero_secrets(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", "master\n"),
            ("", "0\t0\n"),
            ("error listing secrets", ""),  # secret list fails
        ]

        result = git_ops.branch_info()

        assert result.secret_count == 0

    def test_returns_branch_info_dataclass(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "feature-branch\n"),
            ("", "1\t5\n"),
        ]

        result = git_ops.branch_info()

        assert isinstance(result, BranchInfo)
        assert result == BranchInfo(name="feature-branch", ahead=5, behind=1, secret_count=0)


class TestGitOpsApplyPatch:
    def test_success(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_ops.apply_patch("diff --git a/.bashrc\n-old\n+new")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg apply --cached" in cmd

    def test_failure(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("error: patch does not apply", "")

        result = git_ops.apply_patch("bad patch")

        assert result.success is False
        assert result.error is not None

    def test_temp_file_cleaned_up_on_success(
        self, git_ops: GitOps, shell: MagicMock
    ) -> None:
        shell.exe.return_value = ("", "")

        git_ops.apply_patch("diff content")

        cmd = shell.exe.call_args[0][0]
        # Extract the temp file path from the command
        parts = cmd.split("cfg apply --cached ")
        assert len(parts) == 2
        tmpfile = parts[1].strip()
        assert not Path(tmpfile).exists()

    def test_temp_file_cleaned_up_on_failure(
        self, git_ops: GitOps, shell: MagicMock
    ) -> None:
        shell.exe.return_value = ("apply failed", "")

        git_ops.apply_patch("bad patch")

        cmd = shell.exe.call_args[0][0]
        parts = cmd.split("cfg apply --cached ")
        assert len(parts) == 2
        tmpfile = parts[1].strip()
        assert not Path(tmpfile).exists()


class TestGitOpsApplyPatchReverse:
    def test_success(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_ops.apply_patch_reverse("diff --git a/.bashrc\n-old\n+new")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg apply --cached --reverse" in cmd

    def test_failure(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.exe.return_value = ("error: patch does not apply", "")

        result = git_ops.apply_patch_reverse("bad patch")

        assert result.success is False
        assert result.error is not None
