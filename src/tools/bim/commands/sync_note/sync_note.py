from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import tzlocal
from buvis.pybase.filesystem import atomic_write_text
from buvis.pybase.result import CommandResult
from buvis.pybase.zettel import ReadZettelUseCase
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase
from buvis.pybase.zettel.domain.entities import ProjectZettel

from bim.integrations.jira_adapter import ZettelJiraAdapter
from bim.params.sync_note import SyncNoteParams

if TYPE_CHECKING:
    from pathlib import Path

    from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository

DEFAULT_JIRA_IGNORE_US_LABEL = "do-not-track"


def _extract_issue_key(md_link: str) -> str | None:
    """Extract issue key from markdown link like [PROJ-123](url)."""
    if md_link.startswith("["):
        end = md_link.find("]")
        if end > 1:
            return md_link[1:end]
    return None


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

    def execute(self) -> CommandResult:
        match self.params.target_system:
            case "jira":
                self._target = ZettelJiraAdapter(self.jira_adapter_config)
            case _:
                return CommandResult(
                    success=False,
                    error=f"Target system '{self.params.target_system}' not supported",
                )
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
                warning, message, count = self._update_existing_issue(current_us, project)
                if warning:
                    warnings.append(warning)
                if message:
                    messages.append(message)
                synced_count += count
                continue

            messages.append(self._create_issue(path, project))
            synced_count += 1

        return CommandResult(
            success=True,
            output="\n".join(messages),
            warnings=warnings,
            metadata={"synced_count": synced_count},
        )

    def _create_issue(self, path: Path, project: ProjectZettel) -> str:
        new_issue = self._target.create_from_project(project)
        md_style_link = f"[{new_issue.id}]({new_issue.link})"
        project.us = md_style_link
        timestamp = datetime.now(tzlocal.get_localzone()).strftime("%Y-%m-%d %H:%M")
        project.add_log_entry(
            f"- [i] {timestamp} - Jira Issue created: {md_style_link}",
        )
        formatted_content = PrintZettelUseCase(self.formatter).execute(project.get_data())
        atomic_write_text(path, formatted_content)
        return f"Jira Issue {new_issue.id} created from {path}"

    def _update_existing_issue(
        self,
        current_us: str,
        project: ProjectZettel,
    ) -> tuple[str | None, str | None, int]:
        """Return (warning, message, count) for the caller to append/accumulate."""
        issue_key = _extract_issue_key(current_us)
        if not issue_key:
            return f"Can't parse issue key from: {current_us}", None, 0
        updated = self._target.update_description_from_project(issue_key, project)
        if updated:
            return None, f"Description updated for {issue_key}", 1
        return None, f"Already in sync with {issue_key}", 0
