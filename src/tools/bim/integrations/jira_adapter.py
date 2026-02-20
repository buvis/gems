from __future__ import annotations

from typing import TYPE_CHECKING, Any

from buvis.pybase.adapters.jira.jira import JiraAdapter
from buvis.pybase.adapters.jira.settings import JiraSettings
from buvis.pybase.zettel.integrations.jira.assemblers.project_zettel_jira_issue import (
    ProjectZettelJiraIssueDTOAssembler,
)

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.entities import ProjectZettel


class ZettelJiraAdapter(JiraAdapter):
    """JiraAdapter that can create issues from ProjectZettel."""

    def __init__(self, config: dict[str, Any]) -> None:
        settings = JiraSettings(**{k: v for k, v in config.items() if k in JiraSettings.model_fields})
        super().__init__(settings)
        self._config = config

    def create_from_project(self, project: ProjectZettel) -> Any:
        defaults = self._config.get("defaults")
        if not isinstance(defaults, dict):
            msg = f"Can't get the defaults from:\n{defaults}"
            raise ValueError(msg)
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults=defaults.copy())
        dto = assembler.to_dto(project)
        return self.create(dto)
