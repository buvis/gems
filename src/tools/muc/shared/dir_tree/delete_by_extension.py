from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult

from .safe_rglob import safe_rglob


def delete_by_extension(directory: Path, extensions_to_delete: list[str]) -> CommandResult:
    """Delete files with specific extensions in the given directory.

    Args:
        directory: Path to the directory to process.
        extensions_to_delete: List of file extensions to delete.

    Returns:
        Completed actions and recoverable failures.
    """
    result = CommandResult(success=True)
    for file_path in safe_rglob(directory):
        if file_path.parent.stem == ".stfolder":  ## keep content of sensitive folders
            continue
        try:
            if file_path.is_file() and file_path.suffix.lower() in extensions_to_delete:
                file_path.unlink()
                result.info.append(f"Removed extra file {file_path}")
        except OSError as exc:
            result.warnings.append(f"Could not remove extra file {file_path}: {exc}")
    return result
