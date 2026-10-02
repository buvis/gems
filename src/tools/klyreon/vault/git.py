"""Git layer and autonomy gate (spec; PRD "Git layer and autonomy gate").

The seam that separates machine writes from human ones:

- :func:`commit` stages and commits EXACTLY the given paths with a per-invocation
  klyreon identity, so a human's uncommitted edit elsewhere survives untouched
  and the user's global git config is never written. ``git add -A`` is never used.
- :func:`is_git_vault` / :func:`require_git_for_autonomy` are the gate the
  mutating commands reserved by later PRDs (ingest, maintain) consult.
- :func:`is_human_authored` reads ``git log`` author names: any commit whose
  author is not the klyreon identity means a human touched the file.

Every subprocess call is non-interactive and scoped with ``git -C <root>``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from buvis.pybase.result import CommandResult

__all__ = [
    "GitError",
    "GitIdentity",
    "commit",
    "is_git_vault",
    "is_human_authored",
    "require_git_for_autonomy",
]

_GIT_MISSING_WARNING = (
    "vault root is not inside a git work tree: autonomous commands (ingest, "
    "maintain) are refused there because neither the git archive pruning relies "
    "on nor authorship detection exists. Run 'git init' in the vault root to enable them."
)


class GitError(RuntimeError):
    """Raised when a git subprocess fails."""


@dataclass(frozen=True, slots=True)
class GitIdentity:
    """The klyreon author identity applied per commit."""

    name: str
    email: str


def _run_git(root: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run ``git -C <root> <args>`` capturing text output, non-interactively."""
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        msg = f"git {' '.join(args)} failed: {completed.stderr.strip()}"
        raise GitError(msg)
    return completed


def is_git_vault(root: Path) -> bool:
    """Return ``True`` when ``root`` is inside a git work tree."""
    completed = _run_git(root, ["rev-parse", "--is-inside-work-tree"], check=False)
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def require_git_for_autonomy(root: Path) -> CommandResult:
    """Gate for mutating autonomous commands.

    Returns a failing :class:`CommandResult` carrying the warning text when the
    vault is not a git work tree, else a success result.
    """
    if is_git_vault(root):
        return CommandResult(success=True)
    return CommandResult(success=False, error=_GIT_MISSING_WARNING)


def commit(root: Path, paths: list[str], subject: str, identity: GitIdentity) -> str:
    """Stage and commit exactly ``paths`` under the klyreon identity.

    Args:
        root: The vault root (a git work tree).
        paths: Vault-relative paths to stage and commit. Pathspec scoping is
            what leaves a human's uncommitted edit elsewhere modified and unstaged.
        subject: The commit subject line.
        identity: The per-invocation author name/email.

    Returns:
        The new commit SHA.

    Raises:
        GitError: when staging or committing fails, or ``paths`` is empty.
    """
    if not paths:
        msg = "commit requires at least one path (git add -A is never used)"
        raise GitError(msg)

    _run_git(root, ["add", "--", *paths])
    _run_git(
        root,
        [
            "-c",
            f"user.name={identity.name}",
            "-c",
            f"user.email={identity.email}",
            # Machine commits are made under the klyreon identity, which has no
            # GPG key; sign-off with the user's key would misattribute them. We
            # disable signing per-invocation (never touching global config), so
            # authorship stays detectable by name (see is_human_authored).
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            subject,
            "--",
            *paths,
        ],
    )
    sha = _run_git(root, ["rev-parse", "HEAD"]).stdout.strip()
    return sha


def is_human_authored(root: Path, path: str, identity: GitIdentity) -> bool:
    """Return ``True`` when any commit touching ``path`` is NOT the klyreon identity.

    A path with no git history is not human-authored (``False``).
    """
    completed = _run_git(root, ["log", "--format=%an", "--", path], check=False)
    if completed.returncode != 0:
        return False
    authors = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return any(author != identity.name for author in authors)
