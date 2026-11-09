from __future__ import annotations

from typing import Any

from buvis.pybase.formatting import StringOperator
from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ContactTemplate:
    """A person at ``contact/<slug>.md``; the vault's ``page.convert-to-contact-person.tpl``."""

    name = "contact"
    folder = "contact"
    file_stem = "slug"
    default_tags = ["person"]

    def questions(self) -> list[Question]:
        return [
            Question(key="company", prompt="Company", default=""),
            Question(key="job-title", prompt="Job title", default=""),
            Question(key="email", prompt="Email address", default=""),
        ]

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        title = " ".join(word[:1].upper() + word[1:] for word in str(answers.get("title", "")).split(" "))
        slug = StringOperator.slugify(title)
        data = ZettelData()
        data.metadata["type"] = "contact"
        data.metadata["title"] = title
        data.metadata["contact-type"] = "person"
        data.metadata["summary"] = ""
        data.metadata["company"] = answers.get("company", "")
        data.metadata["job-title"] = answers.get("job-title", "")
        data.metadata["email"] = answers.get("email", "")
        tags_raw = answers.get("tags", "")
        if tags_raw:
            data.metadata["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        data.sections = [
            (f"# {title}", f"![{title} photo|180]({slug}.jpeg)"),
            ("## First contact", ""),
            ("## Timeline", ""),
            ("## Relationships", ""),
        ]
        return data

    def hooks(self) -> list[Hook]:
        return []
