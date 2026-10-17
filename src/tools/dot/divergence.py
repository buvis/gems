"""Save, locate and count divergence patches."""

from __future__ import annotations

import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.filesystem import atomic_write_bytes

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter

__all__ = ["divergence_dir", "pending_patch_warning", "save_divergence_patch"]


def divergence_dir(root: str | Path) -> Path:
    """Return the directory holding divergence patches.

    Args:
        root: Dotfiles root directory.

    Returns:
        The divergence patch directory under the dotfiles root.
    """
    return Path(root) / ".local/share/dot/divergence"


def pending_patch_warning(root: str | Path) -> str | None:
    """Describe pending divergence patches.

    Args:
        root: Dotfiles root directory.

    Returns:
        A warning naming the patch count and directory, or None when no patch is pending.
    """
    d = divergence_dir(root)
    n = len(list(d.glob("*.patch"))) if d.is_dir() else 0
    if n == 0:
        return None
    return f"{n} divergence patch(es) pending in {d}"


def _diff_argv(dotfiles_root: str, selected: list[str]) -> list[str]:
    return [
        "git",
        f"--git-dir={dotfiles_root}/.buvis",
        f"--work-tree={dotfiles_root}",
        "--literal-pathspecs",
        "diff",
        "--binary",
        "--full-index",
        "--no-renames",
        # Keep user diff config (external tools, textconv, color, prefixes) out of the patch.
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "HEAD",
        "--",
        *selected,
    ]


def save_divergence_patch(
    shell: ShellAdapter, dotfiles_root: str, selected: list[str]
) -> tuple[Path | None, str | None]:
    """Write the HEAD-to-worktree diff of ``selected`` to a new patch file.

    Args:
        shell: Shell adapter with the ``cfg`` alias for the bare repo.
        dotfiles_root: Work-tree root holding the bare ``.buvis`` repository.
        selected: Paths to save.

    Returns:
        The patch path, or the reason the save failed.
    """
    wd = Path(dotfiles_root)
    err, head = shell.exe("cfg rev-parse HEAD", wd)
    if err or not head.strip():
        return None, f"cannot read HEAD: {err or 'empty output'}"
    err, upstream = shell.exe("cfg rev-parse @{u}", wd)
    if err or not upstream.strip():
        return None, f"cannot read upstream: {err or 'empty output'}"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    patch = divergence_dir(wd) / f"{stamp}.patch"
    header = (
        "# dot divergence patch\n"
        f"# base: {head.strip()}\n"
        f"# upstream: {upstream.strip()}\n"
        f"# host: {socket.gethostname()}\n\n"
    )
    argv = _diff_argv(dotfiles_root, selected)
    try:
        # Patches hold private dotfile bytes: keep the directory owner-only.
        patch.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if patch.exists():
            return None, f"{patch} already exists"
        # Raw bytes via a fixed argv: ShellAdapter.exe decodes text and would rewrite CRLF.
        proc = subprocess.run(argv, cwd=wd, capture_output=True, text=False, check=False)
        if proc.returncode != 0:
            return None, proc.stderr.decode(errors="replace").strip() or f"git diff exited {proc.returncode}"
        atomic_write_bytes(patch, header.encode() + proc.stdout)
    except OSError as exc:
        return None, str(exc)
    return patch, None
