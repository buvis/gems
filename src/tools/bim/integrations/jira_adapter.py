from __future__ import annotations

from typing import Any

from buvis.pybase.adapters.jira.jira import JiraAdapter
from buvis.pybase.adapters.jira.settings import JiraSettings
from buvis.pybase.zettel.domain.entities import ProjectZettel
from buvis.pybase.zettel.integrations.jira.assemblers.project_zettel_jira_issue import (
    ProjectZettelJiraIssueDTOAssembler,
)


class ZettelJiraAdapter(JiraAdapter):
    """JiraAdapter that can create issues from ProjectZettel."""

    def __init__(self, config: dict[str, Any]) -> None:
        settings = JiraSettings(**{k: v for k, v in config.items() if k in JiraSettings.model_fields})
        super().__init__(settings)
        self._config = config

    def _get_assembler(self) -> ProjectZettelJiraIssueDTOAssembler:
        defaults = self._config.get("defaults")
        if not isinstance(defaults, dict):
            msg = f"Can't get the defaults from:\n{defaults}"
            raise ValueError(msg)
        return ProjectZettelJiraIssueDTOAssembler(defaults=defaults.copy())

    def create_from_project(self, project: ProjectZettel) -> Any:
        assembler = self._get_assembler()
        dto = assembler.to_dto(project)
        return self.create(dto)

    def update_description_from_project(self, issue_key: str, project: ProjectZettel) -> bool:
        """Push zettel description to Jira. Returns True if updated."""
        assembler = self._get_assembler()
        dto = assembler.to_dto(project)
        current = self.get(issue_key)
        if current.description != dto.description:
            self.update(issue_key, {"description": dto.description})
            return True
        return False
