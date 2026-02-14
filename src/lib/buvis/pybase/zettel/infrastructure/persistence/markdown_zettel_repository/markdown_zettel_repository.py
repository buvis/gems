from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from buvis.pybase.zettel.domain.entities.project.project import ProjectZettel
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def _default_cache_path() -> str:
    xdg = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(xdg, "buvis", "zettel_cache.bin")


def _create_zettel(data: ZettelData, *, from_rust: bool = False) -> Zettel:
    if data.metadata.get("type") == "project":
        return ProjectZettel(data, from_rust=from_rust)
    return Zettel(data, from_rust=from_rust)

try:
    from buvis.pybase.zettel._core import load_all, load_filtered, parse_file

    _HAS_RUST = True
except ImportError:
    _HAS_RUST = False


def _rust_dict_to_zettel_data(raw: dict[str, Any]) -> ZettelData:
    """Convert the dict returned by Rust _core into a ZettelData instance."""
    data = ZettelData()
    data.metadata = dict(raw.get("metadata", {}))
    data.reference = dict(raw.get("reference", {}))
    data.sections = [(h, c) for h, c in raw.get("sections", [])]
    data.file_path = raw.get("file_path") or None
    return data


class MarkdownZettelRepository(ZettelRepository):
    def __init__(
        self,
        zettelkasten_path: Path | None = None,
        extensions: list[str] | None = None,
    ) -> None:
        self.zettelkasten_path = zettelkasten_path
        self._extensions = extensions or ["md"]

    def save(self, zettel: Zettel) -> None:
        from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
            MarkdownZettelFormatter,
        )

        data = zettel.get_data()
        if not data.file_path:
            raise ValueError("Cannot save zettel without file_path")
        formatted = MarkdownZettelFormatter.format(data)
        Path(data.file_path).write_text(formatted, encoding="utf-8")

    def find_by_id(self, zettel_id: str) -> Zettel:
        if self.zettelkasten_path is None:
            raise ValueError("zettelkasten_path required for find_by_id")
        path = self.zettelkasten_path / f"{zettel_id}.md"
        return self.find_by_location(str(path))

    def find_by_location(self, repository_location: str) -> Zettel:
        if _HAS_RUST:
            raw = parse_file(repository_location)
            zettel_data = _rust_dict_to_zettel_data(raw)
            return _create_zettel(zettel_data, from_rust=True)

        # Fallback to pure-Python parser
        from pathlib import Path

        from buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser import (
            ZettelFileParser,
        )

        zettel_data = ZettelFileParser.from_file(Path(repository_location))
        return _create_zettel(zettel_data)

    def find_all(
        self,
        directory: str,
        metadata_eq: dict[str, Any] | None = None,
    ) -> list[Zettel]:
        if _HAS_RUST:
            if metadata_eq:
                cp = _default_cache_path()
                raw_list = load_filtered(directory, self._extensions, metadata_eq, cp)
            else:
                raw_list = load_all(directory, self._extensions)
            return [
                _create_zettel(_rust_dict_to_zettel_data(raw), from_rust=True)
                for raw in raw_list
            ]

        from pathlib import Path

        from buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser import (
            ZettelFileParser,
        )

        exts = self._extensions
        dir_path = Path(directory).expanduser().resolve()
        zettels: list[Zettel] = []
        for ext in exts:
            for file_path in sorted(dir_path.rglob(f"*.{ext}")):
                zettel_data = ZettelFileParser.from_file(file_path)
                if metadata_eq and not all(
                    zettel_data.metadata.get(k) == v for k, v in metadata_eq.items()
                ):
                    continue
                zettel_data.file_path = str(file_path)
                zettels.append(_create_zettel(zettel_data))
        return zettels
