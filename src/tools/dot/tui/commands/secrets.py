from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from dot.git.service import DotGitService

__all__ = [
    "SecretEntry",
    "hide_all",
    "list_secrets",
    "register_secret",
    "reveal_all",
    "unregister_secret",
]


@dataclass(frozen=True)
class SecretEntry:
    path: str
    status: str


def list_secrets(git_ops: DotGitService) -> list[SecretEntry]:
    if not git_ops.is_secret_tool_available():
        return []

    root = git_ops.wd
    entries: list[SecretEntry] = []
    for p in git_ops.list_secrets():
        if not p:
            continue
        if (root / p).exists():
            status = "revealed"
        else:
            status = "hidden"
        entries.append(SecretEntry(path=p, status=status))
    return entries


def register_secret(git_ops: DotGitService, path: str) -> CommandResult:
    if not git_ops.is_secret_tool_available():
        return CommandResult(success=False, error="git-secret not installed")

    return git_ops.register_secret(path)


def unregister_secret(git_ops: DotGitService, path: str) -> CommandResult:
    if not git_ops.is_secret_tool_available():
        return CommandResult(success=False, error="git-secret not installed")

    return git_ops.unregister_secret(path)


def reveal_all(git_ops: DotGitService, passphrase: str | None = None) -> CommandResult:
    if not git_ops.is_secret_tool_available():
        return CommandResult(success=False, error="git-secret not installed")

    return git_ops.reveal_secrets(passphrase)


def hide_all(git_ops: DotGitService) -> CommandResult:
    if not git_ops.is_secret_tool_available():
        return CommandResult(success=False, error="git-secret not installed")

    return git_ops.hide_secrets()
