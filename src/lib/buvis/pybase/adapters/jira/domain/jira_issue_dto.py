from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JiraIssueDTO:
    """DTO for JIRA issue creation.

    Maps Python fields to JIRA API field names. Custom field IDs are
    configured via JiraSettings.field_mappings.

    Attributes:
        project: JIRA project key (e.g., 'BUV').
        title: Issue summary text, maps to JIRA 'summary'.
        description: Issue body text.
        issue_type: Type name (e.g., 'Task', 'Bug').
        labels: List of label strings.
        priority: Priority name (e.g., 'Medium', 'High').
        ticket: Parent ticket reference (custom field).
        feature: Feature/epic link (custom field).
        assignee: Assignee username key.
        reporter: Reporter username key.
        team: Team name (custom field), None if not set.
        region: Region value (custom field), None if not set.
        id: Server-assigned issue key (e.g., 'BUV-123'), populated after creation.
        link: Permalink URL, populated after creation.
    """

    project: str
    title: str
    description: str
    issue_type: str
    labels: list[str]
    priority: str
    ticket: str
    feature: str
    assignee: str
    reporter: str
    team: str | None
    region: str | None
    id: str | None = None
    link: str | None = None
