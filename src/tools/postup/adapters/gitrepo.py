"""Git CLI delegation for per-repo local signals.

Every method shells out to ``git`` and returns typed data. A non-zero exit or
missing binary raises :class:`GitError`; the command layer catches it and
degrades the failure into that repo's ``errors`` rather than crashing.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from postup.domain.contracts import Branches, BranchInfo, Commit, LocalState

__all__ = ["GitError", "GitRepoAdapter"]

_REMOTE_RE = re.compile(r"github\.com[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
_UNIT = "\x1f"
_MAX_COMMITS = 200
_MAX_BRANCHES = 50
_GIT_TIMEOUT = 120
_FETCH_TIMEOUT = 180


class GitError(RuntimeError):
    """Raised when a git subprocess fails or produces unusable output."""


class GitRepoAdapter:
    """Run ``git`` against one repository checkout.

    Args:
        path: Absolute path to the repository working tree.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def _run(self, args: list[str], *, timeout: int = _GIT_TIMEOUT) -> str:
        """Run ``git <args>`` in the repo, returning stdout.

        Raises:
            GitError: On a non-zero exit, a missing binary, or a timeout.
        """
        try:
            proc = subprocess.run(  # fixed argv, no shell
                ["git", *args],
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitError(f"git {args[0]}: {exc}") from exc
        if proc.returncode != 0:
            raise GitError(f"git {args[0]}: {proc.stderr.strip()[:300]}")
        return proc.stdout

    def slug(self) -> tuple[str, str]:
        """Return ``(owner, name)`` parsed from the ``origin`` remote URL.

        Raises:
            GitError: If ``origin`` is missing or not a GitHub remote.
        """
        url = self._run(["remote", "get-url", "origin"]).strip()
        match = _REMOTE_RE.search(url)
        if not match or match.group(1) in (".", "..") or match.group(2) in (".", ".."):
            raise GitError(f"not a github remote: {url}")
        return match.group(1), match.group(2)

    def fetch(self) -> None:
        """Refresh remotes with a quiet ``git fetch origin``."""
        self._run(["fetch", "--quiet", "origin"], timeout=_FETCH_TIMEOUT)

    def current_branch(self) -> str:
        """Return the current branch name (``HEAD`` symbolic ref)."""
        return self._run(["rev-parse", "--abbrev-ref", "HEAD"]).strip()

    def commits(self, branch: str, days: int) -> list[Commit]:
        """Return commits on ``origin/branch`` within the last ``days`` days."""
        out = self._run(
            [
                "log",
                f"origin/{branch}",
                f"--since={days} days ago",
                f"--max-count={_MAX_COMMITS}",
                "--date=short",
                f"--pretty=%h{_UNIT}%ad{_UNIT}%an{_UNIT}%s",
            ],
        )
        commits: list[Commit] = []
        for line in out.splitlines():
            if _UNIT not in line:
                continue
            sha, date, author, subject = line.split(_UNIT)
            commits.append(Commit(sha=sha, date=date, author=author, subject=subject))
        return commits

    def commit_count(self, branch: str, days: int) -> int:
        """Return the true commit total on ``origin/branch`` in the window."""
        out = self._run(["rev-list", "--count", f"--since={days} days ago", f"origin/{branch}"])
        return int(out.strip() or "0")

    def last_tag(self, branch: str) -> str | None:
        """Return the most recent tag reachable from ``origin/branch``."""
        try:
            tag = self._run(["describe", "--tags", "--abbrev=0", f"origin/{branch}"]).strip()
        except GitError:
            return None
        return tag or None

    def unreleased_commits(self, branch: str, last_tag: str) -> int | None:
        """Return commits on ``origin/branch`` since ``last_tag``."""
        try:
            out = self._run(["rev-list", "--count", f"{last_tag}..origin/{branch}"])
        except GitError:
            return None
        return int(out.strip() or "0")

    def branches(self, branch: str, current: str) -> Branches:
        """Return stray branches (not the default branch) and extra worktrees."""
        merged = set(
            self._run(
                ["branch", "-a", "--merged", f"origin/{branch}", "--format=%(refname:short)"],
            ).split(),
        )
        keep = {f"origin/{branch}", "origin/HEAD", "origin", branch, current}
        stray: list[BranchInfo] = []
        for ref in ("refs/remotes/origin", "refs/heads"):
            out = self._run(
                ["for-each-ref", ref, "--format=%(refname:short)" + _UNIT + "%(committerdate:short)"],
            )
            for line in out.splitlines():
                if _UNIT not in line:
                    continue
                name, date = line.split(_UNIT)
                if name in keep:
                    continue
                stray.append(BranchInfo(name=name, date=date, merged=name in merged))
        worktrees = [
            line[len("worktree ") :]
            for line in self._run(["worktree", "list", "--porcelain"]).splitlines()
            if line.startswith("worktree ")
        ][1:]
        stray.sort(key=lambda b: b.date)
        return Branches(stray=stray[:_MAX_BRANCHES], worktrees=worktrees)

    def local_state(self, branch: str, current: str) -> LocalState:
        """Return dirty/ahead/behind/stash state relative to ``origin/branch``."""
        status_lines = [line for line in self._run(["status", "--porcelain"]).splitlines() if line]
        ahead = behind = 0
        try:
            behind_str, ahead_str = self._run(
                ["rev-list", "--left-right", "--count", f"origin/{branch}...HEAD"],
            ).split()
            ahead, behind = int(ahead_str), int(behind_str)
        except (GitError, ValueError):
            pass
        stashes = len(self._run(["stash", "list"]).splitlines())
        return LocalState(
            branch=current,
            dirty=len(status_lines),
            ahead=ahead,
            behind=behind,
            stashes=stashes,
        )
