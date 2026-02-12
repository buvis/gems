from __future__ import annotations

from typing import Any

from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelReader
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

try:
    from buvis.pybase.zettel._core import load_all, parse_file

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


class MarkdownZettelRepository(ZettelReader):
    def find_by_location(self, repository_location: str) -> Zettel:
        if _HAS_RUST:
            raw = parse_file(repository_location)
            zettel_data = _rust_dict_to_zettel_data(raw)
            return Zettel(zettel_data, from_rust=True)

        # Fallback to pure-Python parser
        from pathlib import Path

        from buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser import (
            ZettelFileParser,
        )

        zettel_data = ZettelFileParser.from_file(Path(repository_location))
        return Zettel(zettel_data)

    def find_all(self, directory: str, extensions: list[str] | None = None) -> list[Zettel]:
        if _HAS_RUST:
            raw_list = load_all(directory, extensions)
            zettels: list[Zettel] = []
            for raw in raw_list:
                zettel_data = _rust_dict_to_zettel_data(raw)
                zettels.append(Zettel(zettel_data, from_rust=True))
            return zettels

        from pathlib import Path

        from buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser import (
            ZettelFileParser,
        )

        exts = extensions or ["md"]
        dir_path = Path(directory).expanduser().resolve()
        zettels = []
        for ext in exts:
            for file_path in sorted(dir_path.rglob(f"*.{ext}")):
                zettel_data = ZettelFileParser.from_file(file_path)
                zettel_data.file_path = str(file_path)
                zettels.append(Zettel(zettel_data))
        return zettels

