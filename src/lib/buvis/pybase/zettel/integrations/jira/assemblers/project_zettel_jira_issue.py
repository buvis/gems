from __future__ import annotations

from typing import Any

from buvis.pybase.adapters.jira.domain.jira_issue_dto import JiraIssueDTO
from buvis.pybase.zettel.domain.entities.project.project import ProjectZettel


def _get_field(source: ProjectZettel, key: str, default: Any = None) -> Any:
    """Look up a field in reference then metadata (reference wins, matching old _alias_attributes merge)."""
    val = source.data.reference.get(key)
    if val is None:
        val = source.data.metadata.get(key)
    return val if val is not None else default


class ProjectZettelJiraIssueDTOAssembler:
    def __init__(self, defaults: dict[str, Any] | None = None) -> None:
        self.defaults = defaults or {}

    def _require_default(self, key: str) -> Any:
        val = self.defaults.get(key)
        if not val:
            msg = f"Default {key} is required"
            raise ValueError(msg)
        return val

    def to_dto(self, source: ProjectZettel) -> JiraIssueDTO:
        project = self._require_default("project")
        region = self._require_default("region")
        user = self._require_default("user")
        team = self._require_default("team")

        if _get_field(source, "deliverable") == "enhancement":
            issue_type = self.defaults["enhancements"]["issue_type"]
            feature = self.defaults["enhancements"]["feature"]
            labels = self.defaults["enhancements"]["labels"].split(",")
            priority = self.defaults["enhancements"]["priority"]
        else:
            issue_type = self.defaults["bugs"]["issue_type"]
            feature = self.defaults["bugs"]["feature"]
            labels = self.defaults["bugs"]["labels"].split(",")
            priority = self.defaults["bugs"]["priority"]

        description = "No description provided"

        for section in source.data.sections:
            title, content = section
            if title == "## Description":
                description = content.strip()

        ticket_references = _get_ticket_references(source)

        if ticket_references != "":
            description += f"\n\n{ticket_references}"

        title = source.title or ""

        if "pex" in (source.tags or []):
            title = f"PEX: {title}"

        return JiraIssueDTO(
            project=project,
            title=title,
            description=description,
            issue_type=issue_type,
            labels=labels,
            priority=priority,
            ticket=_get_field(source, "ticket", ""),
            feature=feature,
            assignee=user,
            reporter=user,
            team=team,
            region=region,
        )


def _get_ticket_references(source: ProjectZettel) -> str:
    ref_text = ""
    ticket = _get_field(source, "ticket")
    ticket_related = _get_field(source, "ticket-related") or _get_field(source, "ticket_related")

    if ticket is not None:
        ref_text = f"This solves SR {ticket}."

    if ticket_related is not None:
        ticket_list = sorted(ticket_related.split(" "))

        if len(ticket_list) > 1:
            if len(ticket_list) == 2:
                ticket_list_str = " and ".join(ticket_list)
            else:
                ticket_list_str = ", ".join(ticket_list[:-1]) + ", and " + ticket_list[-1]
            ref_text += f" Related SRs: {ticket_list_str}."
        else:
            ref_text += f" Related SR: {ticket_related}."

    return ref_text
