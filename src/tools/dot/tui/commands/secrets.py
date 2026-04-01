from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from dot.tui.git_ops import GitOps

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


def _git_secret_available(git_ops: GitOps) -> bool:
    return git_ops.shell.is_command_available("git-secret")


def list_secrets(git_ops: GitOps) -> list[SecretEntry]:
    if not _git_secret_available(git_ops):
        return []

    err, out = git_ops.shell.exe("cfg secret list", git_ops.wd)
    if err or not out.strip():
        return []

    root = Path(git_ops.dotfiles_root)
    entries: list[SecretEntry] = []
    for line in out.strip().splitlines():
        p = line.strip()
        if not p:
            continue
        if (root / p).exists():
            status = "revealed"
        else:
            status = "hidden"
        entries.append(SecretEntry(path=p, status=status))
    return entries


def register_secret(git_ops: GitOps, path: str) -> CommandResult:
    if not _git_secret_available(git_ops):
        return CommandResult(success=False, error="git-secret not installed")

    err, _out = git_ops.shell.exe(f"cfg secret add {shlex.quote(path)}", git_ops.wd)
    if err:
        return CommandResult(success=False, error=err)
    return CommandResult(success=True)


def unregister_secret(git_ops: GitOps, path: str) -> CommandResult:
    if not _git_secret_available(git_ops):
        return CommandResult(success=False, error="git-secret not installed")

    err, _out = git_ops.shell.exe(f"cfg secret remove {shlex.quote(path)}", git_ops.wd)
    if err:
        return CommandResult(success=False, error=err)
    return CommandResult(success=True)


def reveal_all(git_ops: GitOps, passphrase: str | None = None) -> CommandResult:
    if not _git_secret_available(git_ops):
        return CommandResult(success=False, error="git-secret not installed")

    cmd = "cfg secret reveal -f"
    if passphrase:
        cmd += f" -p {shlex.quote(passphrase)}"
    err, _out = git_ops.shell.exe(cmd, git_ops.wd)
    if err:
        return CommandResult(success=False, error=err)
    return CommandResult(success=True)


def hide_all(git_ops: GitOps) -> CommandResult:
    if not _git_secret_available(git_ops):
        return CommandResult(success=False, error="git-secret not installed")

    err, _out = git_ops.shell.exe("cfg secret hide", git_ops.wd)
    if err:
        return CommandResult(success=False, error=err)
    return CommandResult(success=True)
