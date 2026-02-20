from __future__ import annotations

import shutil
from pathlib import Path

from buvis.pybase.result import CommandResult


class CommandFlatten:
    def __init__(self, source: str, destination: str) -> None:
        self.source = Path(source)
        self.destination = Path(destination)

    def execute(self) -> CommandResult:
        warnings: list[str] = []
        copied = 0

        self.destination.mkdir(parents=True, exist_ok=True)

        for item in self.source.rglob("*"):
            if not item.is_file():
                continue
            if item.name.startswith("."):
                continue

            try:
                dest = self._resolve_collision(self.destination / item.name)
                shutil.copy2(item, dest)
                copied += 1
            except Exception as exc:
                warnings.append(f"Failed to copy {item}: {exc}")

        return CommandResult(
            success=True,
            output=f"Copied {copied} file(s) to {self.destination}",
            warnings=warnings,
        )

    @staticmethod
    def _resolve_collision(dest: Path) -> Path:
        if not dest.exists():
            return dest
        stem = dest.stem
        suffix = dest.suffix
        parent = dest.parent
        counter = 1
        while True:
            candidate = parent / f"{stem}-{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
