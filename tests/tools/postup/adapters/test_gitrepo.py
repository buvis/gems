from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from postup.adapters.gitrepo import GitError, GitRepoAdapter

_UNIT = "\x1f"


class _Proc:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _patch_run(mocker, mapping: dict[str, _Proc], default: _Proc | None = None):
    """Patch subprocess.run to dispatch on the git subcommand (args[0][1])."""

    def fake_run(argv, **_kwargs):
        sub = argv[1]
        if sub in mapping:
            return mapping[sub]
        if default is not None:
            return default
        return _Proc()

    return mocker.patch("postup.adapters.gitrepo.subprocess.run", side_effect=fake_run)


class TestSlug:
    def test_parses_github_ssh_remote(self, mocker):
        _patch_run(mocker, {"remote": _Proc(stdout="git@github.com:buvis/gems.git\n")})
        assert GitRepoAdapter(Path("/r")).slug() == ("buvis", "gems")

    def test_parses_github_https_remote(self, mocker):
        _patch_run(mocker, {"remote": _Proc(stdout="https://github.com/buvis/gems\n")})
        assert GitRepoAdapter(Path("/r")).slug() == ("buvis", "gems")

    def test_non_github_remote_raises(self, mocker):
        _patch_run(mocker, {"remote": _Proc(stdout="https://gitlab.com/x/y.git\n")})
        with pytest.raises(GitError, match="not a github remote"):
            GitRepoAdapter(Path("/r")).slug()

    def test_nonzero_exit_raises(self, mocker):
        _patch_run(mocker, {"remote": _Proc(stderr="no remote", returncode=1)})
        with pytest.raises(GitError):
            GitRepoAdapter(Path("/r")).slug()

    def test_missing_binary_raises(self, mocker):
        mocker.patch("postup.adapters.gitrepo.subprocess.run", side_effect=FileNotFoundError("git"))
        with pytest.raises(GitError):
            GitRepoAdapter(Path("/r")).slug()


class TestCommits:
    def test_parses_commit_lines(self, mocker):
        out = _UNIT.join(["abc123", "2026-09-01", "bob", "fix things"]) + "\n"
        _patch_run(mocker, {"log": _Proc(stdout=out)})
        commits = GitRepoAdapter(Path("/r")).commits("main", 60)
        assert len(commits) == 1
        assert commits[0].sha == "abc123"
        assert commits[0].subject == "fix things"

    def test_ignores_malformed_lines(self, mocker):
        _patch_run(mocker, {"log": _Proc(stdout="garbage-no-unit\n")})
        assert GitRepoAdapter(Path("/r")).commits("main", 60) == []

    def test_commit_count(self, mocker):
        _patch_run(mocker, {"rev-list": _Proc(stdout="42\n")})
        assert GitRepoAdapter(Path("/r")).commit_count("main", 60) == 42


class TestBranches:
    def test_stray_branches_and_worktrees(self, mocker):
        merged = "origin/main\norigin/old-feature\n"
        refs = f"origin/main{_UNIT}2026-01-01\norigin/old-feature{_UNIT}2026-02-01\norigin/HEAD{_UNIT}2026-01-01\n"
        worktrees = "worktree /main/checkout\nworktree /extra/wt\n"

        def fake_run(argv, **_kwargs):
            sub = argv[1]
            if sub == "branch":
                return _Proc(stdout=merged)
            if sub == "for-each-ref":
                return _Proc(stdout=refs) if argv[2] == "refs/remotes/origin" else _Proc(stdout="")
            if sub == "worktree":
                return _Proc(stdout=worktrees)
            return _Proc()

        mocker.patch("postup.adapters.gitrepo.subprocess.run", side_effect=fake_run)
        result = GitRepoAdapter(Path("/r")).branches("main", "main")

        names = [b.name for b in result.stray]
        assert "origin/old-feature" in names
        assert "origin/main" not in names  # default branch kept out
        assert result.worktrees == ["/extra/wt"]  # first (main) worktree dropped
        assert next(b for b in result.stray if b.name == "origin/old-feature").merged is True


class TestLocalState:
    def test_dirty_ahead_behind_stashes(self, mocker):
        def fake_run(argv, **_kwargs):
            sub = argv[1]
            if sub == "status":
                return _Proc(stdout=" M file.py\n?? new.py\n")
            if sub == "rev-list":
                return _Proc(stdout="1\t3\n")  # behind=1, ahead=3
            if sub == "stash":
                return _Proc(stdout="stash@{0}\n")
            return _Proc()

        mocker.patch("postup.adapters.gitrepo.subprocess.run", side_effect=fake_run)
        state = GitRepoAdapter(Path("/r")).local_state("main", "feature")
        assert state.branch == "feature"
        assert state.dirty == 2
        assert state.ahead == 3
        assert state.behind == 1
        assert state.stashes == 1


class TestReleaseHelpers:
    def test_last_tag_none_when_git_fails(self, mocker):
        _patch_run(mocker, {"describe": _Proc(stderr="no tag", returncode=1)})
        assert GitRepoAdapter(Path("/r")).last_tag("main") is None

    def test_unreleased_commits_counts(self, mocker):
        _patch_run(mocker, {"rev-list": _Proc(stdout="7\n")})
        assert GitRepoAdapter(Path("/r")).unreleased_commits("main", "v1.0.0") == 7


def test_fetch_timeout_raises(mocker):
    mocker.patch(
        "postup.adapters.gitrepo.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="git fetch", timeout=180),
    )
    with pytest.raises(GitError):
        GitRepoAdapter(Path("/r")).fetch()
