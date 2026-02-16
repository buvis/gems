from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import tzlocal
from bim.dependencies import get_formatter, get_repo
from buvis.pybase.adapters import JiraAdapter, console
from buvis.pybase.zettel import ReadZettelUseCase
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase
from buvis.pybase.zettel.domain.entities import ProjectZettel
from buvis.pybase.zettel.integrations.jira.assemblers.project_zettel_jira_issue import (
    ProjectZettelJiraIssueDTOAssembler,
)

DEFAULT_JIRA_IGNORE_US_LABEL = "do-not-track"


class DictConfig:
    """Shim providing Configuration-like interface over a dict."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get_configuration_item(self, key: str) -> Any:
        return self._data[key]

    def get_configuration_item_or_default(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class ZettelJiraAdapter(JiraAdapter):  # type: ignore[misc]
    """JiraAdapter that can create issues from ProjectZettel."""

    def __init__(self, cfg: DictConfig) -> None:
        super().__init__(cfg)
        self._cfg = cfg

    def create_from_project(self, project: ProjectZettel) -> Any:
        defaults = self._cfg.get_configuration_item("defaults")
        if not isinstance(defaults, dict):
            msg = f"Can't get the defaults from:\n{defaults}"
            raise ValueError(msg)
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults=defaults.copy())
        dto = assembler.to_dto(project)
        return self.create(dto)


class CommandSyncNote:
    def __init__(
        self,
        path_note: Path,
        target_system: str,
        jira_adapter_config: dict[str, Any],
    ) -> None:
        if not path_note.is_file():
            raise FileNotFoundError(f"Note not found: {path_note}")
        self.path_note = path_note
        self.jira_adapter_config = jira_adapter_config

        match target_system:
            case "jira":
                jira_cfg = DictConfig(jira_adapter_config)
                self._target = ZettelJiraAdapter(jira_cfg)
            case _:
                raise NotImplementedError(f"Target system '{target_system}' not supported")

    def execute(self) -> None:
        repo = get_repo()
        reader = ReadZettelUseCase(repo)
        note = reader.execute(str(self.path_note))

        if isinstance(note, ProjectZettel):
            project: ProjectZettel = note
        else:
            console.failure(f"{self.path_note} is not a project")
            return

        ignore_flag = self.jira_adapter_config.get("ignore", DEFAULT_JIRA_IGNORE_US_LABEL)

        if not hasattr(project, "us") or not project.us:
            new_issue = self._target.create_from_project(project)
            md_style_link = f"[{new_issue.id}]({new_issue.link})"
            project.us = md_style_link
            timestamp = datetime.now(tzlocal.get_localzone()).strftime("%Y-%m-%d %H:%M")
            project.add_log_entry(
                f"- [i] {timestamp} - Jira Issue created: {md_style_link}",
            )
            formatted_content = PrintZettelUseCase(get_formatter()).execute(project.get_data())
            self.path_note.write_bytes(formatted_content.encode("utf-8"))
            console.success(f"Jira Issue {new_issue.id} created from {self.path_note}")
        elif note.us == ignore_flag:
            console.warning("Project is set to ignore Jira")
        else:
            console.success(f"Already linked to {note.us}")
