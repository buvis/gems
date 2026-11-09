from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

POST_PROCESSING = (
    "Don't forget to write a summary into frontmatter!\n\n"
    "Go through the log and record actions into GTD lists below.\n\n"
    "#gtd/act/now\n\n#gtd/act/next\n\n#gtd/wait\n\n#gtd/act/someday"
)


class MeetingMinutesTemplate:
    """Dated minutes with the GTD block; the vault's ``page.convert-to-meeting-minutes.tpl``."""

    name = "meeting-minutes"
    body_section = "## Log"

    def questions(self) -> list[Question]:
        return [
            Question(
                key="location",
                prompt="Location",
                choices=["webex", "teams", "phone", "face to face"],
                required=True,
            ),
            Question(key="organizer", prompt="Organizer", default=""),
        ]

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        now = datetime.now().astimezone().replace(microsecond=0)
        subject = re.sub(r"\s*meeting minutes$", "", str(answers.get("title", "")).strip(), flags=re.IGNORECASE)
        if not subject:
            raise ValueError("meeting title needs a subject, not just 'meeting minutes'")
        title = f"{now:%Y-%m-%d} | {subject[0].upper() + subject[1:]} meeting minutes"
        data = ZettelData()
        data.metadata["type"] = "meeting-minutes"
        data.metadata["title"] = title
        data.metadata["date"] = now
        data.metadata["location"] = answers.get("location", "")
        data.metadata["start"] = "hh:mm"
        data.metadata["end"] = "hh:mm"
        data.metadata["organizer"] = answers.get("organizer", "")
        data.metadata["attendees"] = [""]
        data.metadata["summary"] = ""
        tags_raw = answers.get("tags", "")
        if tags_raw:
            data.metadata["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        data.sections = [
            (f"# {title}", ""),
            ("## Agenda", ""),
            ("## Log", ""),
            ("## Post-processing", POST_PROCESSING),
        ]
        return data

    def hooks(self) -> list[Hook]:
        return []
