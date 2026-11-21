from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult

from .safe_rglob import safe_rglob


def remove_empty_directories(directory: Path) -> CommandResult:
    """Remove empty directories in the given directory.

    Args:
        directory: Path to the directory to process.

    Returns:
        Completed actions and recoverable failures.
    """
    result = CommandResult(success=True)
    for dir_path in sorted(safe_rglob(directory), reverse=True):
        try:
            empty = dir_path.is_dir() and not any(dir_path.iterdir())
        except OSError as exc:
            result.warnings.append(f"Could not read directory {dir_path}: {exc}")
            continue
        if not empty:
            continue
        try:
            dir_path.rmdir()
            result.info.append(f"Removed empty directory {dir_path}")
        except OSError as exc:
            result.warnings.append(f"Could not remove empty directory {dir_path}: {exc}")
    return result
