from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult

from .safe_rglob import safe_rglob


def lowercase_file_extensions(directory: Path) -> CommandResult:
    """Convert all file extensions to lowercase in the given directory.

    Args:
        directory: Path to the directory to process.

    Returns:
        Completed actions and recoverable failures.
    """
    result = CommandResult(success=True)
    for file_path in safe_rglob(directory):
        try:
            if file_path.is_file():
                new_name = file_path.stem + file_path.suffix.lower()
                new_path = file_path.with_name(new_name)

                if new_name != file_path.name:
                    file_path.rename(new_path)
                    result.info.append(f"Renamed {file_path} -> {new_name}")
        except OSError as exc:
            result.warnings.append(f"Could not lowercase extension of {file_path}: {exc}")
    return result
