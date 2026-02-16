from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelWriter
from buvis.pybase.zettel.domain.services.zettel_factory import ZettelFactory
from buvis.pybase.zettel.domain.templates import HookRunner, ZettelTemplate


class CreateZettelUseCase:
    def __init__(
        self,
        zettelkasten_path: Path,
        writer: ZettelWriter,
        hook_runner: HookRunner | None = None,
    ) -> None:
        self.zettelkasten_path = zettelkasten_path
        self.writer = writer
        self.hook_runner = hook_runner

    def execute(self, template: ZettelTemplate, answers: dict[str, Any]) -> Path:
        data = template.build_data(answers)
        zettel = Zettel(data)
        zettel = ZettelFactory.create(zettel)
        path = self.zettelkasten_path / f"{zettel.id}.md"
        if path.exists():
            raise FileExistsError(f"Zettel already exists: {path}")
        zettel.get_data().file_path = str(path)
        self.writer.save(zettel)
        if self.hook_runner:
            self.hook_runner(template.hooks(), zettel.get_data(), self.zettelkasten_path)
        return path
