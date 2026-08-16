from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dot.git.models import BranchInfo, FileEntry
from dot.git.service import DotGitService


@pytest.fixture
def shell() -> MagicMock:
    mock = MagicMock()
    mock.exe.return_value = ("", "")
    return mock


@pytest.fixture
def git_service(shell: MagicMock) -> DotGitService:
    svc = DotGitService(shell=shell, dotfiles_root="/home/user/dotfiles")
    shell.exe.reset_mock()
    return svc


class TestDotGitServiceConstruction:
    def test_alias_embeds_literal_dotfiles_root(self, shell: MagicMock) -> None:
        DotGitService(shell=shell, dotfiles_root="/home/user/dotfiles")

        shell.alias.assert_called_once()
        alias_name, alias_cmd = shell.alias.call_args[0]
        assert alias_name == "cfg"
        assert "/home/user/dotfiles" in alias_cmd
        assert "${DOTFILES_ROOT}" not in alias_cmd

    def test_alias_ignores_dotfiles_root_env_var(self, shell: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", "/should/not/be/used")

        DotGitService(shell=shell, dotfiles_root="/home/user/dotfiles")

        alias_cmd = shell.alias.call_args[0][1]
        assert "/home/user/dotfiles" in alias_cmd
        assert "/should/not/be/used" not in alias_cmd

    def test_does_not_modify_os_environ(self, shell: MagicMock) -> None:
        before = dict(os.environ)

        DotGitService(shell=shell, dotfiles_root="/home/user/dotfiles")

        assert dict(os.environ) == before

    def test_checks_fetch_refspec_first(self, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "+refs/heads/*:refs/remotes/origin/*")

        DotGitService(shell=shell, dotfiles_root="/home/user/dotfiles")

        first_cmd = shell.exe.call_args_list[0][0][0]
        assert "cfg config remote.origin.fetch" in first_cmd

    def test_does_not_reset_fetch_refspec_when_already_configured(self, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "+refs/heads/*:refs/remotes/origin/*")

        DotGitService(shell=shell, dotfiles_root="/home/user/dotfiles")

        assert shell.exe.call_count == 1

    def test_resets_fetch_refspec_when_check_errors(self, shell: MagicMock) -> None:
        shell.exe.return_value = ("fatal: not found", "")

        DotGitService(shell=shell, dotfiles_root="/home/user/dotfiles")

        assert shell.exe.call_count == 2

    def test_resets_fetch_refspec_when_check_returns_empty(self, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        DotGitService(shell=shell, dotfiles_root="/home/user/dotfiles")

        assert shell.exe.call_count == 2


class TestDotGitServiceStatus:
    def test_empty_output_returns_empty_list(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        entries, hide_error = git_service.status()

        assert entries == []
        assert hide_error is None

    def test_porcelain_command_error_returns_empty_list(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("fatal: not a git repository", "")

        entries, _hide_error = git_service.status()

        assert entries == []

    def test_modified_staged(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "M  .bashrc")

        entries, _hide_error = git_service.status()

        assert FileEntry(path=".bashrc", status="M ") in entries

    def test_modified_unstaged(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", " M .bashrc")

        entries, _hide_error = git_service.status()

        assert FileEntry(path=".bashrc", status=" M") in entries

    def test_added_staged(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "A  .newrc")

        entries, _hide_error = git_service.status()

        assert FileEntry(path=".newrc", status="A ") in entries

    def test_deleted_unstaged(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", " D .oldrc")

        entries, _hide_error = git_service.status()

        assert FileEntry(path=".oldrc", status=" D") in entries

    def test_untracked(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "?? newfile.txt")

        entries, _hide_error = git_service.status()

        assert FileEntry(path="newfile.txt", status="??") in entries

    def test_multiple_files(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "M  .bashrc\n M .vimrc\n?? new.txt")

        entries, _hide_error = git_service.status()

        assert len(entries) == 3

    def test_both_staged_and_unstaged_same_file(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "MM .bashrc")

        entries, _hide_error = git_service.status()

        assert FileEntry(path=".bashrc", status="MM") in entries

    def test_file_with_spaces_in_path(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "M  my config file.txt")

        entries, _hide_error = git_service.status()

        assert FileEntry(path="my config file.txt", status="M ") in entries

    def test_unmerged_conflict_status_code_produces_entry(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "UU merge.txt")

        entries, _hide_error = git_service.status()

        assert FileEntry(path="merge.txt", status="UU") in entries

    def test_non_secret_file_not_marked_as_secret(self, git_service: DotGitService, shell: MagicMock) -> None:
        # ".ssh/config.secret" is the realistic ciphertext path git-secret leaves in the
        # worktree after a hide; ".ssh/config" itself is gitignored and can never appear
        # in porcelain output.
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", ""),  # cfg secret hide -m
            ("", "M  .bashrc\n M .ssh/config.secret"),  # cfg status --porcelain
            ("", ".ssh/config\n"),  # cfg secret list
        ]

        entries, hide_error = git_service.status()

        bashrc = next(f for f in entries if f.path == ".bashrc")
        assert bashrc.is_secret is False
        assert hide_error is None

    def test_file_marked_as_secret_when_path_in_secret_list(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", ""),  # cfg secret hide -m
            ("", "M  .bashrc\n M .ssh/config.secret"),  # cfg status --porcelain
            ("", ".ssh/config.secret\n"),  # cfg secret list
        ]

        entries, _hide_error = git_service.status()

        secret_entry = next(f for f in entries if f.path == ".ssh/config.secret")
        assert secret_entry.is_secret is True

        secret_list_cmd = shell.exe.call_args_list[2][0][0]
        assert "cfg secret list" in secret_list_cmd

    def test_git_secret_unavailable_all_not_secret(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "M  .bashrc\nM  .ssh/config")

        entries, _hide_error = git_service.status()

        assert all(not f.is_secret for f in entries)

    def test_git_secret_list_error_all_not_secret(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", ""),  # cfg secret hide -m
            ("", "M  .bashrc"),  # cfg status --porcelain
            ("error getting secrets", ""),  # cfg secret list fails
        ]

        entries, _hide_error = git_service.status()

        assert all(not f.is_secret for f in entries)

    def test_first_call_is_porcelain_when_secret_unavailable(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "M  .bashrc")

        git_service.status()

        first_cmd = shell.exe.call_args_list[0][0][0]
        assert "cfg status --porcelain" in first_cmd

    def test_hide_failure_still_returns_entries_with_hide_error(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("permission denied", ""),  # cfg secret hide -m fails
            ("", " M .ssh/config.secret"),  # cfg status --porcelain still runs
            ("", ".ssh/config\n"),  # cfg secret list
        ]

        entries, hide_error = git_service.status()

        assert entries != []
        assert any(f.path == ".ssh/config.secret" for f in entries)
        assert hide_error is not None
        assert "permission denied" in hide_error

        hide_cmd = shell.exe.call_args_list[0][0][0]
        status_cmd = shell.exe.call_args_list[1][0][0]
        assert "cfg secret hide -m" in hide_cmd
        assert "cfg status --porcelain" in status_cmd

    def test_hide_success_returns_entries_with_no_hide_error(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", ""),  # cfg secret hide -m succeeds
            ("", "M  .bashrc"),  # cfg status --porcelain
            ("", ""),  # cfg secret list
        ]

        entries, hide_error = git_service.status()

        assert entries != []
        assert hide_error is None

    def test_modified_secret_file_visible_without_prior_status_call(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        """Regression coverage: the secret hide step runs on every status() call, so a
        modified secret is visible with no prior CLI ``dot status`` run required.
        git-secret re-encrypts the plaintext into a ciphertext file, so a modified secret
        shows up in porcelain as the unstaged, modified ``<path>.secret`` file - never as
        the (gitignored) plaintext path."""
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", ""),  # cfg secret hide -m
            ("", " M .ssh/config.secret"),  # cfg status --porcelain
            ("", ".ssh/config\n"),  # cfg secret list
        ]

        entries, hide_error = git_service.status()

        hide_cmd = shell.exe.call_args_list[0][0][0]
        status_cmd = shell.exe.call_args_list[1][0][0]
        assert "cfg secret hide -m" in hide_cmd
        assert "cfg status --porcelain" in status_cmd

        secret_entry = next(f for f in entries if f.path == ".ssh/config.secret")
        assert secret_entry.status == " M"
        assert hide_error is None


class TestDotGitServiceDiff:
    def test_unstaged_diff(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "diff --git a/.bashrc b/.bashrc\n-old\n+new")

        result = git_service.diff(".bashrc")

        shell.exe.assert_called_once()
        cmd = shell.exe.call_args[0][0]
        assert "cfg diff" in cmd
        assert "--cached" not in cmd
        assert ".bashrc" in cmd
        assert result == "diff --git a/.bashrc b/.bashrc\n-old\n+new"

    def test_staged_diff(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "diff --git a/.bashrc b/.bashrc\n-old\n+new")

        git_service.diff(".bashrc", staged=True)

        cmd = shell.exe.call_args[0][0]
        assert "--cached" in cmd
        assert ".bashrc" in cmd

    def test_returns_output_text(self, git_service: DotGitService, shell: MagicMock) -> None:
        expected = "--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new"
        shell.exe.return_value = ("", expected)

        result = git_service.diff("file")

        assert result == expected

    def test_returns_empty_on_no_diff(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_service.diff("file")

        assert result == ""


class TestDotGitServiceBranchInfo:
    def test_parses_branch_name(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "master\n"),  # rev-parse --abbrev-ref HEAD
            ("", "0\t0\n"),  # rev-list --count --left-right
        ]

        result = git_service.branch_info()

        assert result.name == "master"

    def test_parses_ahead_behind(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "main\n"),  # rev-parse
            ("", "2\t3\n"),  # rev-list: 2 behind, 3 ahead
        ]

        result = git_service.branch_info()

        assert result.ahead == 3
        assert result.behind == 2

    def test_parses_secret_count(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", "master\n"),  # rev-parse
            ("", "0\t0\n"),  # rev-list
            ("", ".ssh/config\n.gnupg/keys\n"),  # secret list
        ]

        result = git_service.branch_info()

        assert result.secret_count == 2

    def test_parses_secret_count_three_entries(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", "master\n"),  # rev-parse
            ("", "0\t0\n"),  # rev-list
            ("", ".ssh/config\n.gnupg/keys\n.aws/credentials\n"),  # secret list
        ]

        result = git_service.branch_info()

        assert result.secret_count == 3

    def test_no_git_secret_zero_secrets(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "master\n"),
            ("", "0\t0\n"),
        ]

        result = git_service.branch_info()

        assert result.secret_count == 0

    def test_defaults_when_rev_parse_fails(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("fatal: not a git repo", ""),  # rev-parse fails
            ("fatal: no upstream", ""),  # rev-list @{u} fails
            ("fatal: no remote", ""),  # rev-list origin/unknown fails
        ]

        result = git_service.branch_info()

        assert result.name == "unknown"
        assert result.ahead == 0
        assert result.behind == 0

    def test_defaults_when_rev_list_fails(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "master\n"),  # rev-parse ok
            ("fatal: no upstream", ""),  # rev-list @{u} fails
            ("fatal: no remote", ""),  # rev-list origin/master fails
        ]

        result = git_service.branch_info()

        assert result.name == "master"
        assert result.ahead == 0
        assert result.behind == 0

    def test_secret_list_error_zero_secrets(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", "master\n"),
            ("", "0\t0\n"),
            ("error listing secrets", ""),  # secret list fails
        ]

        result = git_service.branch_info()

        assert result.secret_count == 0

    def test_returns_branch_info_dataclass(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "feature-branch\n"),
            ("", "1\t5\n"),
        ]

        result = git_service.branch_info()

        assert isinstance(result, BranchInfo)
        assert result == BranchInfo(name="feature-branch", ahead=5, behind=1, secret_count=0)


class TestDotGitServiceHasUncommittedChanges:
    def test_hides_secrets_before_reading_porcelain(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", ""),  # cfg secret hide -m
            ("", " M .ssh/config.secret"),  # cfg status --porcelain
        ]

        result = git_service.has_uncommitted_changes()

        hide_cmd = shell.exe.call_args_list[0][0][0]
        status_cmd = shell.exe.call_args_list[1][0][0]
        assert "cfg secret hide -m" in hide_cmd
        assert "cfg status --porcelain" in status_cmd
        assert result is True

    def test_no_hide_step_when_git_secret_unavailable(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", " M .bashrc")

        result = git_service.has_uncommitted_changes()

        assert result is True
        assert shell.exe.call_count == 1

    def test_hide_failure_does_not_raise_and_dirty_answer_still_true(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("permission denied", ""),  # cfg secret hide -m fails
            ("", " M .ssh/config.secret"),  # cfg status --porcelain still runs
        ]

        result = git_service.has_uncommitted_changes()

        assert result is True

    def test_hide_failure_with_clean_porcelain_returns_false(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("permission denied", ""),  # cfg secret hide -m fails
            ("", ""),  # cfg status --porcelain: clean
        ]

        result = git_service.has_uncommitted_changes()

        assert result is False

    def test_status_command_error_returns_false(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("fatal: not a git repository", "")

        result = git_service.has_uncommitted_changes()

        assert result is False

    def test_true_for_added_file_status(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "A  newfile")

        result = git_service.has_uncommitted_changes()

        assert result is True

    def test_true_for_deleted_file_status(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "D  gone")

        result = git_service.has_uncommitted_changes()

        assert result is True


class TestDotGitServiceHasUnpushedCommits:
    def test_true_when_primary_lookup_reports_unpushed_commits(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.return_value = ("", "2\n")

        result = git_service.has_unpushed_commits()

        assert result is True

    def test_false_when_primary_lookup_reports_zero(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "0\n")

        result = git_service.has_unpushed_commits()

        assert result is False

    def test_only_primary_lookup_runs_when_it_succeeds(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "1\n")

        git_service.has_unpushed_commits()

        assert shell.exe.call_count == 1

    def test_falls_back_to_secondary_lookup_when_primary_errors(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.side_effect = [
            ("fatal: no upstream", ""),  # primary @{u}..HEAD lookup fails
            ("", "3\n"),  # secondary origin/<branch> lookup succeeds
        ]

        result = git_service.has_unpushed_commits()

        assert result is True
        assert shell.exe.call_count == 2

    def test_false_when_secondary_lookup_reports_zero(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("fatal: no upstream", ""),  # primary lookup fails
            ("", "0\n"),  # secondary lookup: nothing unpushed
        ]

        result = git_service.has_unpushed_commits()

        assert result is False

    def test_fails_open_when_both_lookups_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("fatal: no upstream", ""),  # primary lookup fails
            ("fatal: no remote", ""),  # secondary lookup also fails
        ]

        result = git_service.has_unpushed_commits()

        assert result is True


class TestDotGitServiceStage:
    def test_success(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_service.stage(".bashrc")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg add" in cmd
        assert ".bashrc" in cmd

    def test_failure(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("fatal: pathspec 'bad' did not match", "")

        result = git_service.stage("bad")

        assert result.success is False
        assert result.error is not None


class TestDotGitServiceCommit:
    def test_commits_without_secret_hide_when_git_secret_unavailable(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "[master abc1234] my message")

        result = git_service.commit("my message")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg commit -m" in cmd
        assert "my message" in cmd

    def test_hides_secrets_before_committing_when_git_secret_available(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", ""),  # cfg secret hide -m
            ("", "[master abc1234] my message"),  # cfg commit
        ]

        result = git_service.commit("my message")

        assert result.success is True
        assert shell.exe.call_count == 2
        hide_cmd = shell.exe.call_args_list[0][0][0]
        assert "cfg secret hide -m" in hide_cmd
        commit_cmd = shell.exe.call_args_list[1][0][0]
        assert "cfg commit -m" in commit_cmd

    def test_commit_command_failure_returns_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("nothing to commit", "")

        result = git_service.commit("my message")

        assert result.success is False
        assert result.error is not None

    def test_secret_hide_failure_short_circuits_before_commit(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("secret hide error", "")

        result = git_service.commit("my message")

        assert result.success is False
        assert result.error is not None
        assert "secret hide error" in result.error
        assert shell.exe.call_count == 1  # commit itself never ran


class TestDotGitServicePush:
    def test_nothing_to_push_when_no_unpushed_commits(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "0\n")  # rev-list count: 0 unpushed

        result = git_service.push()

        assert result.success is True
        assert result.output == "Nothing to push"
        assert shell.exe.call_count == 1  # only the check, no push

    def test_runs_push_and_succeeds_when_commits_are_unpushed(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.side_effect = [
            ("", "2\n"),  # rev-list count: 2 unpushed
            ("", "Everything up-to-date"),  # cfg push
        ]

        result = git_service.push()

        assert result.success is True
        assert result.output == "Changes pushed"
        push_cmd = shell.exe.call_args_list[1][0][0]
        assert "cfg push" in push_cmd

    def test_push_command_failure_returns_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", "1\n"),  # has unpushed
            ("rejected: non-fast-forward", ""),  # push fails
        ]

        result = git_service.push()

        assert result.success is False
        assert result.error is not None


class TestDotGitServicePull:
    def test_full_flow_succeeds_without_git_secret(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "ok")

        result = git_service.pull()

        assert result.success is True
        assert result.output == "Dotfiles pulled successfully"
        assert shell.exe.call_count == 4  # pull + 3 submodule commands
        cmds = [c[0][0] for c in shell.exe.call_args_list]
        assert "cfg pull" in cmds[0]
        assert "submodule foreach" in cmds[1]
        assert "submodule update --init" in cmds[2]
        assert "submodule update --remote --merge" in cmds[3]

    def test_reveals_secrets_after_submodule_steps_when_git_secret_available(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", "ok")

        result = git_service.pull()

        assert result.success is True
        assert shell.exe.call_count == 5  # pull + 3 submodule + secret reveal
        reveal_cmd = shell.exe.call_args_list[4][0][0]
        assert "cfg secret reveal -f" in reveal_cmd

    def test_passphrase_is_passed_to_secret_reveal_step(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", "ok")

        git_service.pull(passphrase="hunter2")

        reveal_cmd = shell.exe.call_args_list[4][0][0]
        assert "hunter2" in reveal_cmd

    def test_pull_command_failure_returns_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("merge conflict", "")

        result = git_service.pull()

        assert result.success is False

    def test_submodule_reset_failure_short_circuits(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "ok"),  # pull ok
            ("submodule reset error", ""),  # reset step fails
        ]

        result = git_service.pull()

        assert result.success is False
        assert result.error is not None
        assert "submodule reset error" in result.error
        assert shell.exe.call_count == 2

    def test_submodule_init_failure_short_circuits(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "ok"),  # pull ok
            ("", "ok"),  # reset ok
            ("submodule init error", ""),  # init step fails
        ]

        result = git_service.pull()

        assert result.success is False
        assert result.error is not None
        assert "submodule init error" in result.error
        assert shell.exe.call_count == 3

    def test_submodule_update_failure_short_circuits(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "ok"),  # pull ok
            ("", "ok"),  # reset ok
            ("", "ok"),  # init ok
            ("submodule update error", ""),  # update step fails
        ]

        result = git_service.pull()

        assert result.success is False
        assert result.error is not None
        assert "submodule update error" in result.error
        assert shell.exe.call_count == 4

    def test_secret_reveal_failure_short_circuits(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", "ok"),  # pull ok
            ("", "ok"),  # reset ok
            ("", "ok"),  # init ok
            ("", "ok"),  # update ok
            ("secret reveal error", ""),  # reveal fails
        ]

        result = git_service.pull()

        assert result.success is False
        assert result.error is not None
        assert "secret reveal error" in result.error


class TestDotGitServiceAddToGitignore:
    def test_appends_pattern_to_existing_gitignore(self, shell: MagicMock, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        shell.exe.return_value = ("", "")
        service = DotGitService(shell=shell, dotfiles_root=str(tmp_path))

        result = service.add_to_gitignore("node_modules/")

        assert result.success is True
        content = (tmp_path / ".gitignore").read_text()
        assert "node_modules/" in content
        assert "*.pyc" in content

    def test_creates_gitignore_when_missing(self, shell: MagicMock, tmp_path: Path) -> None:
        shell.exe.return_value = ("", "")
        service = DotGitService(shell=shell, dotfiles_root=str(tmp_path))

        result = service.add_to_gitignore("*.log")

        assert result.success is True
        assert (tmp_path / ".gitignore").read_text() == "*.log\n"

    def test_stages_gitignore_after_write(self, shell: MagicMock, tmp_path: Path) -> None:
        shell.exe.return_value = ("", "")
        service = DotGitService(shell=shell, dotfiles_root=str(tmp_path))

        service.add_to_gitignore("tmp/")

        cmd = shell.exe.call_args[0][0]
        assert "cfg add" in cmd
        assert ".gitignore" in cmd

    def test_returns_failure_when_gitignore_write_fails(self, shell: MagicMock, tmp_path: Path) -> None:
        missing_root = tmp_path / "nonexistent"
        service = DotGitService(shell=shell, dotfiles_root=str(missing_root))

        result = service.add_to_gitignore("*.log")

        assert result.success is False
        assert result.error is not None


class TestDotGitServiceApplyPatch:
    def test_success(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_service.apply_patch("diff --git a/.bashrc\n-old\n+new")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg apply --cached" in cmd

    def test_failure(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("error: patch does not apply", "")

        result = git_service.apply_patch("bad patch")

        assert result.success is False
        assert result.error is not None

    def test_temp_file_cleaned_up_on_success(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        git_service.apply_patch("diff content")

        cmd = shell.exe.call_args[0][0]
        parts = cmd.split("cfg apply --cached ")
        assert len(parts) == 2
        tmpfile = parts[1].strip()
        assert not Path(tmpfile).exists()

    def test_temp_file_cleaned_up_on_failure(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("apply failed", "")

        git_service.apply_patch("bad patch")

        cmd = shell.exe.call_args[0][0]
        parts = cmd.split("cfg apply --cached ")
        assert len(parts) == 2
        tmpfile = parts[1].strip()
        assert not Path(tmpfile).exists()

    def test_writes_patch_text_to_temp_file_before_running_command(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        patch = "diff --git a/.bashrc\n-old\n+new"
        recorded_content = []

        def fake_exe(command: str, *args: object, **kwargs: object) -> tuple[str, str]:
            tmpfile = command.split("cfg apply --cached ")[1].strip()
            recorded_content.append(Path(tmpfile).read_text())
            return ("", "")

        shell.exe.side_effect = fake_exe

        git_service.apply_patch(patch)

        assert recorded_content == [patch]


class TestDotGitServiceApplyPatchReverse:
    def test_success(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_service.apply_patch_reverse("diff --git a/.bashrc\n-old\n+new")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg apply --cached --reverse" in cmd

    def test_failure(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("error: patch does not apply", "")

        result = git_service.apply_patch_reverse("bad patch")

        assert result.success is False
        assert result.error is not None

    def test_temp_file_cleaned_up_on_success(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        git_service.apply_patch_reverse("diff content")

        cmd = shell.exe.call_args[0][0]
        parts = cmd.split("cfg apply --cached --reverse ")
        assert len(parts) == 2
        tmpfile = parts[1].strip()
        assert not Path(tmpfile).exists()

    def test_temp_file_cleaned_up_on_failure(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("apply failed", "")

        git_service.apply_patch_reverse("bad patch")

        cmd = shell.exe.call_args[0][0]
        parts = cmd.split("cfg apply --cached --reverse ")
        assert len(parts) == 2
        tmpfile = parts[1].strip()
        assert not Path(tmpfile).exists()

    def test_writes_patch_text_to_temp_file_before_running_command(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        patch = "diff --git a/.bashrc\n-old\n+new"
        recorded_content = []

        def fake_exe(command: str, *args: object, **kwargs: object) -> tuple[str, str]:
            tmpfile = command.split("cfg apply --cached --reverse ")[1].strip()
            recorded_content.append(Path(tmpfile).read_text())
            return ("", "")

        shell.exe.side_effect = fake_exe

        git_service.apply_patch_reverse(patch)

        assert recorded_content == [patch]


class TestDotGitServiceApplyReverseToWorktree:
    def test_success(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_service.apply_reverse_to_worktree("diff --git a/.bashrc\n-old\n+new")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg apply --reverse" in cmd
        assert "--cached" not in cmd

    def test_failure(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("error: patch does not apply", "")

        result = git_service.apply_reverse_to_worktree("bad patch")

        assert result.success is False
        assert result.error == "error: patch does not apply"

    def test_temp_file_cleaned_up_on_success(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        git_service.apply_reverse_to_worktree("diff content")

        cmd = shell.exe.call_args[0][0]
        parts = cmd.split("cfg apply --reverse ")
        assert len(parts) == 2
        tmpfile = parts[1].strip()
        assert not Path(tmpfile).exists()

    def test_temp_file_cleaned_up_on_failure(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("apply failed", "")

        git_service.apply_reverse_to_worktree("bad patch")

        cmd = shell.exe.call_args[0][0]
        parts = cmd.split("cfg apply --reverse ")
        assert len(parts) == 2
        tmpfile = parts[1].strip()
        assert not Path(tmpfile).exists()

    def test_writes_patch_text_to_temp_file_before_running_command(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        patch = "diff --git a/.bashrc\n-old\n+new"
        recorded_content = []

        def fake_exe(command: str, *args: object, **kwargs: object) -> tuple[str, str]:
            tmpfile = command.split("cfg apply --reverse ")[1].strip()
            recorded_content.append(Path(tmpfile).read_text())
            return ("", "")

        shell.exe.side_effect = fake_exe

        git_service.apply_reverse_to_worktree(patch)

        assert recorded_content == [patch]
