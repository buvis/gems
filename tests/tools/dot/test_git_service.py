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


def _service_at(shell: MagicMock, root: Path) -> DotGitService:
    """Build a service rooted at a real directory, with construction calls forgotten."""
    shell.exe.return_value = ("", "")
    service = DotGitService(shell=shell, dotfiles_root=str(root))
    shell.exe.reset_mock()
    return service


class TestDotGitServiceLsFiles:
    def test_returns_tracked_paths_as_set(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", ".bashrc\n.vimrc\n")

        result = git_service.ls_files(".*")

        assert result == {".bashrc", ".vimrc"}

    def test_blank_lines_are_dropped(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", ".bashrc\n\n.vimrc\n\n")

        result = git_service.ls_files(".*")

        assert result == {".bashrc", ".vimrc"}

    def test_no_output_returns_empty_set(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        assert git_service.ls_files("nothing") == set()

    def test_command_error_returns_empty_set(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("fatal: not a git repository", "")

        assert git_service.ls_files(".*") == set()

    def test_quotes_pathspec_and_runs_in_dotfiles_root(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        git_service.ls_files("*.txt")

        cmd, cwd = shell.exe.call_args[0][0], shell.exe.call_args[0][1]
        assert cmd == "cfg ls-files '*.txt'"
        assert str(cwd) == "/home/user/dotfiles"


class TestDotGitServiceCheckIgnore:
    def test_returns_ignored_paths_as_set(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", ".ssh/config\n.aws/credentials\n")

        result = git_service.check_ignore(".*")

        assert result == {".ssh/config", ".aws/credentials"}

    def test_nothing_ignored_returns_empty_set(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        assert git_service.check_ignore(".bashrc") == set()

    def test_command_error_returns_empty_set(self, git_service: DotGitService, shell: MagicMock) -> None:
        # git check-ignore exits non-zero when nothing matches, so an error is a normal outcome
        shell.exe.return_value = ("returned non-zero exit status 1", "")

        assert git_service.check_ignore(".bashrc") == set()

    def test_quotes_pathspec_and_asks_check_ignore(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        git_service.check_ignore("*.log")

        cmd = shell.exe.call_args[0][0]
        assert cmd == "cfg check-ignore '*.log'"


class TestDotGitServiceStageInteractive:
    def test_without_path_starts_patch_mode_over_whole_worktree(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        result = git_service.stage_interactive()

        assert result is None
        shell.exe.assert_not_called()
        assert shell.interact.call_args[0][0] == "cfg add -p"
        assert str(shell.interact.call_args[0][1]) == "/home/user/dotfiles"

    def test_tracked_file_is_staged_in_patch_mode(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", ".bashrc\n")  # ls-files --error-unmatch: file is tracked

        result = git_service.stage_interactive(".bashrc")

        assert result is None
        assert "--error-unmatch" in shell.exe.call_args[0][0]
        interact_cmd = shell.interact.call_args[0][0]
        assert interact_cmd.startswith("cfg add -p")
        assert ".bashrc" in interact_cmd

    def test_untracked_file_is_staged_whole_without_patch_mode(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.return_value = ("Command 'cfg ls-files' returned non-zero exit status 1.", "")

        git_service.stage_interactive("newfile.txt")

        interact_cmd = shell.interact.call_args[0][0]
        assert "-p" not in interact_cmd
        assert interact_cmd.startswith("cfg add")
        assert "newfile.txt" in interact_cmd

    def test_directory_with_untracked_content_gets_intent_to_add_first(
        self, git_service: DotGitService, shell: MagicMock, tmp_path: Path
    ) -> None:
        shell.exe.side_effect = [
            ("", "sub/new.txt\n"),  # ls-files --others --exclude-standard
            ("", ""),  # add --intent-to-add
        ]

        git_service.stage_interactive(str(tmp_path))

        cmds = [c[0][0] for c in shell.exe.call_args_list]
        assert "cfg ls-files --others --exclude-standard" in cmds[0]
        assert "cfg add --intent-to-add" in cmds[1]
        assert str(tmp_path) in cmds[1]
        assert [name for name, _a, _k in shell.mock_calls][-1] == "interact"
        interact_cmd = shell.interact.call_args[0][0]
        assert interact_cmd.startswith("cfg add -p")
        assert str(tmp_path) in interact_cmd

    def test_directory_without_untracked_content_skips_intent_to_add(
        self, git_service: DotGitService, shell: MagicMock, tmp_path: Path
    ) -> None:
        shell.exe.return_value = ("", "\n")  # no untracked files below the directory

        git_service.stage_interactive(str(tmp_path))

        cmds = [c[0][0] for c in shell.exe.call_args_list]
        assert len(cmds) == 1
        assert "--intent-to-add" not in cmds[0]
        assert shell.interact.call_args[0][0].startswith("cfg add -p")


class TestDotGitServiceUnstage:
    def test_single_path_is_reset_and_reported(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_service.unstage("my file.txt")

        assert result.success is True
        assert result.output == "my file.txt unstaged"
        assert shell.exe.call_args[0][0] == "cfg reset HEAD -- 'my file.txt'"

    def test_without_path_everything_is_reset(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_service.unstage()

        assert result.success is True
        assert result.output == "All files unstaged"
        assert shell.exe.call_args[0][0] == "cfg reset HEAD"

    def test_failure_reports_reset_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("fatal: ambiguous argument 'HEAD'", "")

        result = git_service.unstage(".bashrc")

        assert result.success is False
        assert result.error == "Unstage failed: fatal: ambiguous argument 'HEAD'"


class TestDotGitServiceRm:
    def test_plain_file_is_untracked_but_kept_on_disk(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", ".ssh/config\n"),  # cfg secret list: .bashrc is not encrypted
            ("", ""),  # cfg rm --cached
        ]

        result = git_service.rm(".bashrc")

        assert result.success is True
        assert result.output == ".bashrc removed from tracking"
        assert shell.exe.call_args_list[1][0][0] == "cfg rm --cached .bashrc"

    def test_plain_file_removal_failure_reports_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", ""),  # cfg secret list: nothing encrypted
            ("fatal: pathspec '.bashrc' did not match any files", ""),  # cfg rm --cached
        ]

        result = git_service.rm(".bashrc")

        assert result.success is False
        assert result.error is not None
        assert "did not match any files" in result.error

    def test_encrypted_file_removal_runs_git_secret_sequence(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        """Regression guard for the TUI rm action, which used to run a bare ``cfg rm``.

        Every caller now shares this one encrypted-file path: unregister from git-secret,
        untrack the ciphertext, then stage the updated ``.gitsecret/`` mapping.
        """
        shell.exe.side_effect = [
            ("", ".ssh/config\n"),  # cfg secret list: encrypted
            ("", ""),  # cfg secret remove
            ("", ""),  # cfg rm --cached <path>.secret
            ("", ""),  # cfg add .gitsecret/
        ]

        result = git_service.rm(".ssh/config")

        assert result.success is True
        assert result.output == ".ssh/config removed from git-secret, plaintext kept on disk"
        assert [c[0][0] for c in shell.exe.call_args_list] == [
            "cfg secret list",
            "cfg secret remove .ssh/config",
            "cfg rm --cached .ssh/config.secret",
            "cfg add .gitsecret/",
        ]

    def test_partial_line_match_is_not_treated_as_encrypted(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", ".ssh/config.secret\n"),  # only the ciphertext path is listed
            ("", ""),  # cfg rm --cached
        ]

        result = git_service.rm(".ssh/config")

        assert result.output == ".ssh/config removed from tracking"
        assert shell.exe.call_args_list[1][0][0] == "cfg rm --cached .ssh/config"

    def test_git_secret_unregister_failure_stops_before_untracking(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.side_effect = [
            ("", ".ssh/config\n"),  # cfg secret list
            ("gpg: decryption failed", ""),  # cfg secret remove fails
        ]

        result = git_service.rm(".ssh/config")

        assert result.success is False
        assert result.error is not None
        assert "gpg: decryption failed" in result.error
        assert shell.exe.call_count == 2

    def test_ciphertext_untrack_failure_warns_about_changed_mapping(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.side_effect = [
            ("", ".ssh/config\n"),  # cfg secret list
            ("", ""),  # cfg secret remove ok
            ("fatal: pathspec did not match", ""),  # cfg rm --cached <path>.secret fails
        ]

        result = git_service.rm(".ssh/config")

        assert result.success is False
        assert result.error is not None
        assert "already" in result.error
        assert "mapping" in result.error
        assert "cfg checkout -- .gitsecret/" in result.error

    def test_staging_gitsecret_failure_is_only_a_warning(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", ".ssh/config\n"),  # cfg secret list
            ("", ""),  # cfg secret remove
            ("", ""),  # cfg rm --cached <path>.secret
            ("fatal: unable to index file", ""),  # cfg add .gitsecret/ fails
        ]

        result = git_service.rm(".ssh/config")

        assert result.success is True
        assert result.output == ".ssh/config removed from git-secret, plaintext kept on disk"
        assert any("unable to index file" in w for w in result.warnings)

    def test_unreadable_secret_list_falls_back_to_plain_removal_with_warning(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.side_effect = [
            ("git-secret: abort: no keys", ""),  # cfg secret list fails
            ("", ""),  # cfg rm --cached
        ]

        result = git_service.rm(".ssh/config")

        assert result.success is True
        assert result.output == ".ssh/config removed from tracking"
        assert any("no keys" in w for w in result.warnings)

    def test_does_not_depend_on_dotfiles_root_env_var(
        self, git_service: DotGitService, shell: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        before = dict(os.environ)
        shell.exe.side_effect = [
            ("", ".ssh/config\n"),
            ("", ""),
            ("", ""),
            ("", ""),
        ]

        result = git_service.rm(".ssh/config")

        assert result.success is True
        assert str(shell.exe.call_args[0][1]) == "/home/user/dotfiles"
        assert dict(os.environ) == before


class TestDotGitServiceDelete:
    def test_plain_file_is_removed_from_index_and_worktree(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", ""),  # cfg secret list: nothing encrypted
            ("", ""),  # cfg rm
        ]

        result = git_service.delete("my file.txt")

        assert result.success is True
        assert result.output == "my file.txt deleted from dotfiles"
        # ported verbatim from CommandDelete: the pathspec is passed unquoted
        assert shell.exe.call_args_list[1][0][0] == "cfg rm my file.txt"

    def test_plain_file_removal_failure_reports_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", ""),  # cfg secret list
            ("fatal: pathspec 'gone' did not match", ""),  # cfg rm
        ]

        result = git_service.delete("gone")

        assert result.success is False
        assert result.error is not None
        assert "did not match" in result.error

    def test_encrypted_file_is_unregistered_and_erased_from_disk(self, shell: MagicMock, tmp_path: Path) -> None:
        plaintext = tmp_path / "secret.conf"
        plaintext.write_text("token")
        service = _service_at(shell, tmp_path)
        shell.exe.side_effect = [
            ("", "secret.conf\n"),  # cfg secret list
            ("", ""),  # cfg secret remove -c
        ]

        result = service.delete("secret.conf")

        assert result.success is True
        assert result.output == "secret.conf deleted from git-secret and disk"
        assert not plaintext.exists()
        assert [c[0][0] for c in shell.exe.call_args_list] == [
            "cfg secret list",
            "cfg secret remove -c secret.conf",
        ]

    def test_encrypted_file_drops_its_gitignore_line_and_stages_it(self, shell: MagicMock, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.pyc\nsecret.conf\nnode_modules/\n")
        service = _service_at(shell, tmp_path)
        shell.exe.side_effect = [
            ("", "secret.conf\n"),  # cfg secret list
            ("", ""),  # cfg secret remove -c
            ("", ""),  # cfg add .gitignore
        ]

        result = service.delete("secret.conf")

        assert result.success is True
        content = (tmp_path / ".gitignore").read_text()
        assert "secret.conf" not in content
        assert "*.pyc" in content
        assert "node_modules/" in content
        assert shell.exe.call_args_list[2][0][0] == "cfg add .gitignore"

    def test_untouched_gitignore_is_not_staged(self, shell: MagicMock, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        service = _service_at(shell, tmp_path)
        shell.exe.side_effect = [
            ("", "secret.conf\n"),  # cfg secret list
            ("", ""),  # cfg secret remove -c
        ]

        service.delete("secret.conf")

        assert (tmp_path / ".gitignore").read_text() == "*.pyc\n"
        assert all(".gitignore" not in c[0][0] for c in shell.exe.call_args_list)

    def test_git_secret_unregister_failure_keeps_plaintext(self, shell: MagicMock, tmp_path: Path) -> None:
        plaintext = tmp_path / "secret.conf"
        plaintext.write_text("token")
        service = _service_at(shell, tmp_path)
        shell.exe.side_effect = [
            ("", "secret.conf\n"),  # cfg secret list
            ("git-secret: abort: file not found", ""),  # cfg secret remove -c fails
        ]

        result = service.delete("secret.conf")

        assert result.success is False
        assert result.error is not None
        assert "file not found" in result.error
        assert plaintext.exists()

    def test_undeletable_plaintext_reports_hard_error(self, shell: MagicMock, tmp_path: Path) -> None:
        # a directory at the plaintext path exists but cannot be unlinked, so the OS error surfaces
        blocked = tmp_path / "secret.conf"
        blocked.mkdir()
        (blocked / "child").write_text("x")
        service = _service_at(shell, tmp_path)
        shell.exe.side_effect = [
            ("", "secret.conf\n"),  # cfg secret list
            ("", ""),  # cfg secret remove -c
        ]

        result = service.delete("secret.conf")

        assert result.success is False
        assert result.error is not None
        assert result.error.startswith("Failed to delete plaintext:")


class TestDotGitServiceEncryptAndStage:
    def test_registers_encrypts_then_stages(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        result = git_service.encrypt_and_stage(".ssh/config")

        assert result.success is True
        assert result.output == ".ssh/config encrypted and staged"
        assert [c[0][0] for c in shell.exe.call_args_list] == [
            "cfg secret add .ssh/config",
            "cfg secret hide -m",
            "cfg add .ssh/config.secret .gitsecret/ .gitignore",
        ]

    def test_does_not_gate_on_git_secret_availability(self, git_service: DotGitService, shell: MagicMock) -> None:
        # the installed-check belongs to the caller; the service just runs the sequence
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        result = git_service.encrypt_and_stage(".ssh/config")

        assert result.success is True
        assert shell.exe.call_count == 3

    def test_registration_failure_stops_before_hiding(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("git-secret: abort: file not found", "")

        result = git_service.encrypt_and_stage(".ssh/config")

        assert result.success is False
        assert result.error == "Failed to register file: git-secret: abort: file not found"
        assert shell.exe.call_count == 1

    def test_encryption_failure_stops_before_staging(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", ""),  # cfg secret add
            ("gpg: no public key", ""),  # cfg secret hide -m
        ]

        result = git_service.encrypt_and_stage(".ssh/config")

        assert result.success is False
        assert result.error == "Failed to encrypt: gpg: no public key"
        assert shell.exe.call_count == 2

    def test_staging_failure_reports_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.side_effect = [
            ("", ""),  # cfg secret add
            ("", ""),  # cfg secret hide -m
            ("fatal: unable to index file", ""),  # cfg add
        ]

        result = git_service.encrypt_and_stage(".ssh/config")

        assert result.success is False
        assert result.error == "Failed to stage: fatal: unable to index file"


class TestDotGitServiceIsSecretToolAvailable:
    def test_true_when_git_secret_is_installed(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True

        assert git_service.is_secret_tool_available() is True
        assert shell.is_command_available.call_args[0][0] == "git-secret"

    def test_false_when_git_secret_is_missing(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False

        assert git_service.is_secret_tool_available() is False


class TestDotGitServiceListSecrets:
    def test_returns_registered_paths_in_listed_order(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", ".ssh/config\n.aws/credentials\n.ssh/config\n")

        result = git_service.list_secrets()

        assert result == [".ssh/config", ".aws/credentials", ".ssh/config"]
        assert shell.exe.call_args[0][0] == "cfg secret list"

    def test_returns_empty_list_without_git_secret(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False

        assert git_service.list_secrets() == []
        shell.exe.assert_not_called()

    def test_returns_empty_list_when_nothing_registered(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", "\n")

        assert git_service.list_secrets() == []

    def test_returns_empty_list_on_command_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("git-secret: abort: no keys", ".ssh/config\n")

        assert git_service.list_secrets() == []


class TestDotGitServiceRegisterSecret:
    def test_adds_path_to_git_secret(self, git_service: DotGitService, shell: MagicMock) -> None:
        # availability is the caller's concern: the service runs regardless
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        result = git_service.register_secret("my secrets.txt")

        assert result.success is True
        assert shell.exe.call_args[0][0] == "cfg secret add 'my secrets.txt'"

    def test_failure_returns_raw_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("git-secret: abort: file not found", "")

        result = git_service.register_secret(".ssh/config")

        assert result.success is False
        assert result.error == "git-secret: abort: file not found"


class TestDotGitServiceUnregisterSecret:
    def test_removes_path_from_git_secret(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        result = git_service.unregister_secret("my secrets.txt")

        assert result.success is True
        assert shell.exe.call_args[0][0] == "cfg secret remove 'my secrets.txt'"

    def test_failure_returns_raw_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("git-secret: abort: not in .gitsecret", "")

        result = git_service.unregister_secret(".ssh/config")

        assert result.success is False
        assert result.error == "git-secret: abort: not in .gitsecret"


class TestDotGitServiceRevealSecrets:
    def test_reveals_all_secrets_forcefully(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        result = git_service.reveal_secrets()

        assert result.success is True
        assert shell.exe.call_args[0][0] == "cfg secret reveal -f"

    def test_passphrase_is_quoted_and_appended(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        git_service.reveal_secrets("pass phrase")

        assert shell.exe.call_args[0][0] == "cfg secret reveal -f -p 'pass phrase'"

    def test_failure_returns_raw_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("gpg: decryption failed", "")

        result = git_service.reveal_secrets()

        assert result.success is False
        assert result.error == "gpg: decryption failed"


class TestDotGitServiceHideSecrets:
    def test_hides_secrets_without_deleting_plaintext(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        result = git_service.hide_secrets()

        assert result.success is True
        # the explicit action never carries -m: that flag belongs to commit()'s pre-hide step
        assert shell.exe.call_args[0][0] == "cfg secret hide"

    def test_failure_returns_raw_error(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("gpg: no public key", "")

        result = git_service.hide_secrets()

        assert result.success is False
        assert result.error == "gpg: no public key"
