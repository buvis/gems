from __future__ import annotations

from typing import Any

from buvis.pybase.adapters.jira.domain.jira_issue_dto import JiraIssueDTO
from buvis.pybase.zettel.domain.entities.project.project import ProjectZettel


class ProjectZettelJiraIssueDTOAssembler:
    def __init__(self, defaults: dict[str, Any] | None = None) -> None:
        self.defaults = defaults or {}

    def to_dto(self, source: ProjectZettel) -> JiraIssueDTO:
        if not self.defaults.get("project"):
            msg = "Default project is required"
            raise ValueError(msg)

        project = self.defaults["project"]

        if not self.defaults.get("region"):
            msg = "Default region is required"
            raise ValueError(msg)

        region = self.defaults["region"]

        if not self.defaults.get("user"):
            msg = "Default user is required"
            raise ValueError(msg)

        user = self.defaults["user"]

        if not self.defaults.get("team"):
            msg = "Default team is required"
            raise ValueError(msg)

        team = self.defaults["team"]

        if getattr(source, "deliverable", None) == "enhancement":
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
            ticket=getattr(source, "ticket", "") or "",
            feature=feature,
            assignee=user,
            reporter=user,
            team=team,
            region=region,
        )


def _get_ticket_references(source: ProjectZettel) -> str:
    ref_text = ""

    if hasattr(source, "ticket") and source.ticket is not None:
        ref_text = f"This solves SR {source.ticket}."

    if hasattr(source, "ticket_related") and source.ticket_related is not None:
        ticket_list = sorted(source.ticket_related.split(" "))

        if len(ticket_list) > 1:
            if len(ticket_list) == 2:
                ticket_list_str = " and ".join(ticket_list)
            else:
                ticket_list_str = ", ".join(ticket_list[:-1]) + ", and " + ticket_list[-1]
            ref_text += f" Related SRs: {ticket_list_str}."
        else:
            ref_text += f" Related SR: {source.ticket_related}."

    return ref_text
