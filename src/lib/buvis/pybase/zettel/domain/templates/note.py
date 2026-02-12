from __future__ import annotations

from typing import Any

from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class NoteTemplate:
    name = "note"

    def questions(self) -> list[Question]:
        return []

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        data = ZettelData()
        data.metadata["type"] = "note"
        data.metadata["title"] = answers.get("title", "")
        tags_raw = answers.get("tags", "")
        if tags_raw:
            data.metadata["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        data.sections = [(f"# {data.metadata['title']}", "")]
        return data

    def hooks(self) -> list[Hook]:
        return []
