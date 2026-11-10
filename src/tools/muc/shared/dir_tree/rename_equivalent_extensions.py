from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult

from .safe_rglob import safe_rglob


def rename_equivalent_extensions(
    directory: Path,
    equivalent_extensions: list[list[str]],
) -> CommandResult:
    """Rename files based on equivalent extensions.

    Args:
        directory: Path to the directory to process.
        equivalent_extensions: List of lists containing equivalent extensions.
            First item is the target the rest of the list will be renamed to.

    Returns:
        Completed actions and recoverable failures.
    """
    extension_map = {}
    for group in equivalent_extensions:
        target = "." + group[0].lower()
        for ext in group[1:]:
            extension_map["." + ext.lower()] = target

    result = CommandResult(success=True)
    for file_path in safe_rglob(directory):
        try:
            if file_path.is_file():
                current_ext = file_path.suffix.lower()
                if current_ext in extension_map:
                    new_ext = extension_map[current_ext]
                    new_name = file_path.stem + new_ext
                    new_path = file_path.with_name(new_name)
                    file_path.rename(new_path)
                    result.info.append(f"Renamed {file_path} -> {new_name}")
        except OSError as exc:
            result.warnings.append(f"Could not normalize extension of {file_path}: {exc}")
    return result
