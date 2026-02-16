from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import tzlocal
from bim.params.sync_note import SyncNoteParams
from buvis.pybase.result import CommandResult
from buvis.pybase.zettel import ReadZettelUseCase
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase
from buvis.pybase.zettel.domain.entities import ProjectZettel

from bim.integrations.jira_adapter import DictConfig, ZettelJiraAdapter

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository

DEFAULT_JIRA_IGNORE_US_LABEL = "do-not-track"


class CommandSyncNote:
    def __init__(
        self,
        params: SyncNoteParams,
        jira_adapter_config: dict[str, Any],
        repo: ZettelRepository,
        formatter: ZettelFormatter,
    ) -> None:
        self.params = params
        self.jira_adapter_config = jira_adapter_config
        self.repo = repo
        self.formatter = formatter

        match self.params.target_system:
            case "jira":
                jira_cfg = DictConfig(jira_adapter_config)
                self._target = ZettelJiraAdapter(jira_cfg)
            case _:
                raise NotImplementedError(f"Target system '{self.params.target_system}' not supported")

    def execute(self) -> CommandResult:
        messages: list[str] = []
        warnings: list[str] = []
        synced_count = 0

        for path in self.params.paths:
            if not path.is_file():
                warnings.append(f"{path} doesn't exist")
                continue

            reader = ReadZettelUseCase(self.repo)
            note = reader.execute(str(path))

            if isinstance(note, ProjectZettel):
                project: ProjectZettel = note
            else:
                warnings.append(f"{path} is not a project")
                continue

            ignore_flag = self.jira_adapter_config.get("ignore", DEFAULT_JIRA_IGNORE_US_LABEL)
            current_us = getattr(project, "us", None)

            if current_us == ignore_flag:
                warnings.append("Project is set to ignore Jira")
                continue

            if current_us:
                messages.append(f"Already linked to {project.us}")
                continue

            new_issue = self._target.create_from_project(project)
            md_style_link = f"[{new_issue.id}]({new_issue.link})"
            project.us = md_style_link
            timestamp = datetime.now(tzlocal.get_localzone()).strftime("%Y-%m-%d %H:%M")
            project.add_log_entry(
                f"- [i] {timestamp} - Jira Issue created: {md_style_link}",
            )
            formatted_content = PrintZettelUseCase(self.formatter).execute(project.get_data())
            path.write_text(formatted_content, encoding="utf-8")
            messages.append(f"Jira Issue {new_issue.id} created from {path}")
            synced_count += 1

        return CommandResult(
            success=True,
            output="\n".join(messages),
            warnings=warnings,
            metadata={"synced_count": synced_count},
        )
