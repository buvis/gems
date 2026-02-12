from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.services.zettel_factory import ZettelFactory
from buvis.pybase.zettel.domain.templates import ZettelTemplate
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
    MarkdownZettelFormatter,
)


class CreateZettelUseCase:
    def __init__(self, zettelkasten_path: Path) -> None:
        self.zettelkasten_path = zettelkasten_path

    def execute(self, template: ZettelTemplate, answers: dict[str, Any]) -> Path:
        data = template.build_data(answers)
        zettel = Zettel(data)
        zettel = ZettelFactory.create(zettel)
        content = MarkdownZettelFormatter.format(zettel.get_data())
        path = self.zettelkasten_path / f"{zettel.id}.md"
        if path.exists():
            raise FileExistsError(f"Zettel already exists: {path}")
        path.write_bytes(content.encode("utf-8"))
        for hook in template.hooks():
            hook.fn(zettel.get_data(), self.zettelkasten_path)
        return path
