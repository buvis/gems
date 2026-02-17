from __future__ import annotations

from typing import TYPE_CHECKING, Any

from buvis.pybase.adapters.jira.jira import JiraAdapter
from buvis.pybase.zettel.integrations.jira.assemblers.project_zettel_jira_issue import (
    ProjectZettelJiraIssueDTOAssembler,
)

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.entities import ProjectZettel


class DictConfig:
    """Shim providing Configuration-like interface over a dict."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get_configuration_item(self, key: str) -> Any:
        return self._data[key]

    def get_configuration_item_or_default(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class ZettelJiraAdapter(JiraAdapter):
    """JiraAdapter that can create issues from ProjectZettel."""

    def __init__(self, cfg: DictConfig) -> None:
        super().__init__(cfg)  # type: ignore[arg-type]
        self._cfg = cfg

    def create_from_project(self, project: ProjectZettel) -> Any:
        defaults = self._cfg.get_configuration_item("defaults")
        if not isinstance(defaults, dict):
            msg = f"Can't get the defaults from:\n{defaults}"
            raise ValueError(msg)
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults=defaults.copy())
        dto = assembler.to_dto(project)
        return self.create(dto)
