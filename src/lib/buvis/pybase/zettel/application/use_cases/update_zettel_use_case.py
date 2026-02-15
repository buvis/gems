from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelWriter


class UpdateZettelUseCase:
    def __init__(self, writer: ZettelWriter) -> None:
        self.writer = writer

    def execute(
        self, zettel: Zettel, changes: dict[str, Any], target: str = "metadata",
    ) -> None:
        data = zettel.get_data()

        if target == "section":
            for heading, value in changes.items():
                replaced = False
                new_sections: list[tuple[str, str]] = []
                for h, old_body in data.sections:
                    if h == heading:
                        new_sections.append((h, value))
                        replaced = True
                    else:
                        new_sections.append((h, old_body))
                if not replaced:
                    new_sections.append((heading, value))
                data.sections = new_sections
        elif target == "reference":
            data.reference.update(changes)
        else:
            data.metadata.update(changes)

        self.writer.save(zettel)
