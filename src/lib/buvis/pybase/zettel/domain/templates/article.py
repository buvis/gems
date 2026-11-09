from __future__ import annotations

from typing import Any

from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ArticleTemplate:
    """A ``note`` whose backmatter points at the archived original and the web source.

    ``archive_link`` is supplied by the create command once the archive path is
    known; ``web`` is the optional source URL.
    """

    name = "article"

    def questions(self) -> list[Question]:
        return [Question(key="web", prompt="Source URL")]

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        title = answers.get("title", "")
        data = ZettelData()
        data.metadata["type"] = "note"
        data.metadata["title"] = title
        tags_raw = answers.get("tags", "")
        if tags_raw:
            data.metadata["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        data.sections = [(f"# {title}", "")]
        data.reference["article"] = answers.get("archive_link", "")
        web = str(answers.get("web") or "").strip()
        if web:
            data.reference["web"] = f"[{title}]({web})"
        return data

    def hooks(self) -> list[Hook]:
        return []
