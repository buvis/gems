from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult


class CommandDirectorize:
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)

    def execute(self) -> CommandResult:
        warnings: list[str] = []
        processed = 0

        for item in sorted(self.directory.iterdir()):
            if not item.is_file():
                continue
            if item.name.startswith("."):
                continue

            try:
                target_dir = self.directory / item.stem
                target_dir.mkdir(exist_ok=True)
                dest = target_dir / item.name
                if dest.exists():
                    warnings.append(f"Destination exists, skipped: {dest}")
                    continue
                item.rename(dest)
                processed += 1
            except Exception as exc:
                warnings.append(f"Failed to directorize {item.name}: {exc}")

        return CommandResult(
            success=True,
            output=f"Directorized {processed} file(s)",
            warnings=warnings,
        )
