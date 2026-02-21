from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult


class CommandCover:
    def __init__(self: CommandCover, directory: Path) -> None:
        self.directory = directory

    def execute(self: CommandCover) -> CommandResult:
        cleaned_directories = 0
        removed_files = 0
        warnings: list[str] = []

        dirs = [self.directory]
        dirs.extend(d for d in self.directory.rglob("*") if d.is_dir() and not d.is_symlink())

        for current_dir in dirs:
            try:
                cover_files = [
                    candidate
                    for candidate in current_dir.iterdir()
                    if candidate.is_file()
                    and not candidate.is_symlink()
                    and candidate.stem.lower() == "cover"
                    and candidate.suffix.lower() in {".jpg", ".jpeg", ".png"}
                ]
            except OSError as error:
                warnings.append(f"Failed to inspect directory {current_dir}: {error}")
                continue

            if len(cover_files) <= 1:
                continue

            try:
                cover_files_with_mtime = [(path, path.stat().st_mtime) for path in cover_files]
            except OSError as error:
                warnings.append(f"Failed to inspect cover files in {current_dir}: {error}")
                continue

            cleaned_directories += 1
            survivor = min(
                cover_files_with_mtime,
                key=lambda item: (-item[1], item[0].name.lower()),
            )[0]

            for cover_file in cover_files:
                if cover_file == survivor:
                    continue
                try:
                    cover_file.unlink()
                    removed_files += 1
                except OSError as error:
                    warnings.append(f"Failed to delete file {cover_file}: {error}")

            target = survivor.with_name(f"cover{survivor.suffix.lower()}")
            if survivor != target:
                try:
                    survivor.rename(target)
                except OSError as error:
                    warnings.append(f"Failed to rename file {survivor} to {target.name}: {error}")

        if cleaned_directories == 0:
            return CommandResult(success=True, output="No duplicate covers found", warnings=warnings)

        return CommandResult(
            success=True,
            output=f"Cleaned {cleaned_directories} directories, removed {removed_files} files",
            warnings=warnings,
        )
