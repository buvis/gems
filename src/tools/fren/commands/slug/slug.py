from __future__ import annotations

import email
import email.utils
import re
from datetime import timezone
from pathlib import Path

from buvis.pybase.result import CommandResult
from slugify import slugify


class CommandSlug:
    def __init__(self, paths: tuple[str, ...]) -> None:
        self.paths = [Path(p) for p in paths]

    def execute(self) -> CommandResult:
        warnings: list[str] = []
        renamed = 0

        for path in self.paths:
            p = Path(path)
            if not p.exists():
                warnings.append(f"Path not found: {p}")
                continue

            try:
                new_name = self._slugify_name(p)
                if new_name != p.name:
                    dest = self._resolve_collision(p.parent / new_name)
                    p.rename(dest)
                    renamed += 1
            except Exception as exc:
                warnings.append(f"Failed to rename {p.name}: {exc}")

        return CommandResult(
            success=True,
            output=f"Renamed {renamed} file(s)",
            warnings=warnings,
        )

    def _slugify_name(self, path: Path) -> str:
        if path.suffix.lower() == ".eml":
            return self._slugify_eml(path)

        stem = path.stem
        suffix = path.suffix
        slugged = slugify(stem, lowercase=False)
        if not slugged:
            slugged = "unnamed"
        return f"{slugged}{suffix}"

    def _slugify_eml(self, path: Path) -> str:
        try:
            with open(path, "rb") as f:
                msg = email.message_from_binary_file(f)

            date_str = msg.get("Date", "")
            subject = msg.get("Subject", "") or ""

            # Strip Re:/Fw:/Fwd: prefixes
            subject = re.sub(r"^(Re|Fw|Fwd)\s*:\s*", "", subject, flags=re.IGNORECASE).strip()

            # Parse date
            date_prefix = ""
            if date_str:
                try:
                    parsed = email.utils.parsedate_to_datetime(date_str)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    date_prefix = parsed.strftime("%Y-%m-%d_%H%M_")
                except (ValueError, TypeError):
                    pass

            slugged = slugify(subject, lowercase=False) if subject else "unnamed"
            return f"{date_prefix}{slugged}.eml"

        except Exception:
            # Fallback to regular slugify
            return self._slugify_name_plain(path)

    def _slugify_name_plain(self, path: Path) -> str:
        stem = path.stem
        suffix = path.suffix
        slugged = slugify(stem, lowercase=False)
        if not slugged:
            slugged = "unnamed"
        return f"{slugged}{suffix}"

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
