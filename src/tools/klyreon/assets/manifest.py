"""The installed-artifact manifest: one JSON file recording what klyreon put where.

The manifest lives at ``$XDG_STATE_HOME/klyreon/manifest.json`` and tracks every
artifact klyreon installed OUTSIDE the vault (asset packs today; PRD D records
the installed schedule in the same file via the reserved ``kind`` field).

Invariants:

- Written through :func:`buvis.pybase.filesystem.atomic_write_text`. A truncated
  manifest would orphan every installed file, so the write is atomic.
- An unknown ``schema_version`` is rejected loudly (:class:`ManifestError`)
  rather than guessed at.
- A missing manifest means nothing is installed -- that is not an error.
- Entries key on absolute path.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from buvis.pybase.filesystem import atomic_write_text

__all__ = [
    "SCHEMA_VERSION",
    "Manifest",
    "ManifestEntry",
    "ManifestError",
    "entries_for",
    "load_manifest",
    "manifest_path",
    "save_manifest",
]

SCHEMA_VERSION = 1


class ManifestError(ValueError):
    """Raised when the manifest is unreadable or carries an unknown schema version."""


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """One installed artifact. ``kind`` is ``asset`` today; PRD D adds ``schedule``."""

    kind: str
    operator: str
    path: str
    sha256: str
    klyreon_version: str
    installed_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "operator": self.operator,
            "path": self.path,
            "sha256": self.sha256,
            "klyreon_version": self.klyreon_version,
            "installed_at": self.installed_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ManifestEntry:
        missing = [k for k in ("kind", "operator", "path", "sha256", "klyreon_version", "installed_at") if k not in raw]
        if missing:
            msg = f"manifest entry missing required field(s): {', '.join(missing)}"
            raise ManifestError(msg)
        return cls(
            kind=str(raw["kind"]),
            operator=str(raw["operator"]),
            path=str(raw["path"]),
            sha256=str(raw["sha256"]),
            klyreon_version=str(raw["klyreon_version"]),
            installed_at=str(raw["installed_at"]),
        )


@dataclass(slots=True)
class Manifest:
    """The whole record: a schema version and the list of installed entries."""

    schema_version: int = SCHEMA_VERSION
    entries: list[ManifestEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "entries": [e.to_dict() for e in self.entries],
        }

    def entry_for_path(self, path: str) -> ManifestEntry | None:
        """Return the entry keyed on ``path`` (absolute), or ``None``."""
        for entry in self.entries:
            if entry.path == path:
                return entry
        return None

    def upsert(self, entry: ManifestEntry) -> None:
        """Insert ``entry`` or replace the existing one at the same path."""
        for index, existing in enumerate(self.entries):
            if existing.path == entry.path:
                self.entries[index] = entry
                return
        self.entries.append(entry)

    def remove_path(self, path: str) -> None:
        """Drop the entry keyed on ``path`` if present (no error when absent)."""
        self.entries = [e for e in self.entries if e.path != path]


def manifest_path() -> Path:
    """Return the manifest path, honouring ``$XDG_STATE_HOME``."""
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "klyreon" / "manifest.json"


def load_manifest() -> Manifest:
    """Return the parsed manifest, or an empty one when the file is absent.

    A missing file is not an error (nothing installed). Malformed JSON, a
    non-object top level, a non-integer or unknown ``schema_version``, or a
    malformed entry each raise :class:`ManifestError`.
    """
    path = manifest_path()
    if not path.is_file():
        return Manifest()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"manifest is unreadable: {path}: {exc}"
        raise ManifestError(msg) from exc

    if not isinstance(raw, dict):
        msg = f"manifest {path} must be a JSON object, got {type(raw).__name__}"
        raise ManifestError(msg)

    version = raw.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        msg = f"manifest {path} has a non-integer schema_version: {version!r}"
        raise ManifestError(msg)
    if version != SCHEMA_VERSION:
        msg = (
            f"manifest {path} has unknown schema_version {version} "
            f"(this klyreon understands {SCHEMA_VERSION}). Refusing to guess."
        )
        raise ManifestError(msg)

    raw_entries = raw.get("entries", [])
    if not isinstance(raw_entries, list):
        msg = f"manifest {path} 'entries' must be a list, got {type(raw_entries).__name__}"
        raise ManifestError(msg)

    entries = [ManifestEntry.from_dict(e) for e in raw_entries if isinstance(e, dict)]
    if len(entries) != len(raw_entries):
        msg = f"manifest {path} has a non-object entry"
        raise ManifestError(msg)

    return Manifest(schema_version=version, entries=entries)


def save_manifest(manifest: Manifest) -> None:
    """Write ``manifest`` to the manifest path atomically, creating parents."""
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
    atomic_write_text(path, body)


def entries_for(kind: str, operator: str | None = None) -> list[ManifestEntry]:
    """Return manifest entries filtered by ``kind`` and optionally ``operator``.

    Reused by PRD D for ``kind="schedule"``.
    """
    manifest = load_manifest()
    return [e for e in manifest.entries if e.kind == kind and (operator is None or e.operator == operator)]
