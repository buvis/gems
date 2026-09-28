"""Repository discovery by root scan.

Discovers git repositories by walking the settings-defined ``roots`` for a
``.git`` entry, minus the settings-defined ``excludes`` list. No dependency on
gita or any external registry.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from postup.settings import PostupSettings

__all__ = ["discover_repos"]


def _is_repo(path: Path) -> bool:
    """Return True if ``path`` contains a ``.git`` entry (file or directory)."""
    return (path / ".git").exists()


def _scan_root(root: Path, excluded: set[Path], warnings: list[str]) -> list[Path]:
    """Scan one root for repositories, recording a WARN for a bad root.

    A directory holding ``.git`` is a repository and the walk stops descending
    into it. A missing or unreadable root is WARNed and skipped.
    """
    if not root.is_dir():
        warnings.append(f"root not a directory, skipped: {root}")
        return []

    found: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(p for p in current.iterdir() if p.is_dir())
        except OSError as exc:
            warnings.append(f"cannot read {current}, skipped: {exc}")
            continue
        for entry in entries:
            if _is_repo(entry):
                if entry.resolve() not in excluded:
                    found.append(entry.resolve())
                # Stop descending: a repo is a leaf for discovery.
            else:
                stack.append(entry)
    return found


def discover_repos(settings: PostupSettings, warnings: list[str] | None = None) -> list[Path]:
    """Discover repository paths from the configured roots.

    Args:
        settings: Postup settings supplying ``roots`` and ``excludes``.
        warnings: Optional list that WARN messages for bad roots are appended
            to. The caller (the command) surfaces these through the console.

    Returns:
        Deduplicated, sorted list of absolute repository paths.
    """
    warnings = warnings if warnings is not None else []
    excluded = {Path(e).expanduser().resolve() for e in settings.excludes}

    repos: set[Path] = set()
    for raw_root in settings.roots:
        root = Path(raw_root).expanduser()
        repos.update(_scan_root(root, excluded, warnings))

    return sorted(repos)
