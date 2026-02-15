from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelWriter


class DeleteZettelUseCase:
    def __init__(self, writer: ZettelWriter) -> None:
        self.writer = writer

    def execute(self, zettel: Zettel) -> None:
        self.writer.delete(zettel)
