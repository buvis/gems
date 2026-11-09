from __future__ import annotations

from datetime import datetime
from typing import Any

from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ProjectTemplate:
    """Project loop file; the vault's ``page.create-project.tpl``."""

    name = "project"
    body_section = "## Solution"

    def questions(self) -> list[Question]:
        return [
            Question(
                key="deliverable",
                prompt="Deliverable",
                choices=["fix", "enhancement", "support"],
                required=True,
            ),
            Question(key="ticket", prompt="Ticket"),
        ]

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        now = datetime.now().astimezone().replace(microsecond=0)
        title = answers.get("title", "")
        data = ZettelData()
        data.metadata["type"] = "project"
        data.metadata["title"] = title
        data.metadata["date"] = now
        data.metadata["completed"] = False
        # Slot kept in the vault template's order; the create_project_dir hook fills it.
        data.metadata["resources"] = ""
        data.metadata["deliverable"] = answers.get("deliverable", "")
        tags_raw = answers.get("tags", "")
        if tags_raw:
            data.metadata["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        data.sections = [
            (f"# {title}", ""),
            ("## Description", "One paragraph summarizing the problem statement."),
            (
                "## Log",
                f"- [ ] {now:%Y-%m-%d %H:%M} - plan the next action to move this project forward"
                f" | #gtd/act/now 📅 {now:%Y-%m-%d}",
            ),
            ("## Plan", "Plan the steps to complete the project. Use templates for recurring projects."),
            ("## Solution", "Describe what was done to get project closure acceptance."),
        ]
        data.reference["parent"] = ""
        ticket = str(answers.get("ticket") or "").strip()
        if ticket:
            data.reference["ticket"] = ticket
        data.reference["us"] = ""
        data.reference["psd"] = ""
        return data

    def hooks(self) -> list[Hook]:
        return [Hook(name="set_parent_reference"), Hook(name="create_project_dir")]
