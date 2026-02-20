from __future__ import annotations

import unicodedata
from pathlib import Path

from buvis.pybase.result import CommandResult


class CommandNormalize:
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)

    def execute(self) -> CommandResult:
        warnings: list[str] = []
        normalized = 0

        # Bottom-up: deepest dirs first
        dirs = sorted(
            (d for d in self.directory.rglob("*") if d.is_dir()),
            key=lambda p: len(p.parts),
            reverse=True,
        )

        for d in dirs:
            if d.name.startswith("._"):
                continue

            nfc_name = unicodedata.normalize("NFC", d.name)
            if nfc_name == d.name:
                continue

            target = d.parent / nfc_name

            try:
                if target.exists() and target != d:
                    # Merge: move contents into existing target
                    for item in d.iterdir():
                        dest = target / item.name
                        if dest.exists():
                            warnings.append(f"Collision during merge, skipped: {item}")
                            continue
                        item.rename(dest)
                    # Remove empty source dir
                    if not any(d.iterdir()):
                        d.rmdir()
                    else:
                        warnings.append(f"Could not fully merge {d}")
                else:
                    d.rename(target)
                normalized += 1
            except Exception as exc:
                warnings.append(f"Failed to normalize {d}: {exc}")

        return CommandResult(
            success=True,
            output=f"Normalized {normalized} directory name(s)",
            warnings=warnings,
        )
