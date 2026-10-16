"""Location and pending count of saved divergence patches."""

from __future__ import annotations

from pathlib import Path

__all__ = ["divergence_dir", "pending_patch_warning"]


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
