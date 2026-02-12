from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def _create_project_dir(data: ZettelData, zettelkasten_path: Path) -> None:
    project_dir = zettelkasten_path.parent / "projects" / str(data.metadata.get("id", "unknown"))
    project_dir.mkdir(parents=True, exist_ok=True)
    data.metadata["resources"] = f"[project resources]({project_dir.as_uri()})"


class ProjectTemplate:
    name = "project"

    def questions(self) -> list[Question]:
        return [
            Question(
                key="dev_type",
                prompt="Development type",
                choices=["feature", "bugfix", "spike", "maintenance"],
                required=True,
                default="feature",
            ),
        ]

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        data = ZettelData()
        data.metadata["type"] = "project"
        data.metadata["title"] = answers.get("title", "")
        data.metadata["dev-type"] = answers.get("dev_type", "feature")
        data.metadata["completed"] = False
        tags_raw = answers.get("tags", "")
        if tags_raw:
            data.metadata["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        title = data.metadata["title"]
        data.sections = [
            (f"# {title}", ""),
            ("## Description", ""),
            ("## Log", ""),
            ("## Actions buffer", ""),
        ]
        return data

    def hooks(self) -> list[Hook]:
        return [Hook(name="create_project_dir", fn=_create_project_dir)]
