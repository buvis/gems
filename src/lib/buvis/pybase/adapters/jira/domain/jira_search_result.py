from __future__ import annotations

from dataclasses import dataclass

from buvis.pybase.adapters.jira.domain.jira_issue_dto import JiraIssueDTO

__all__ = ["JiraSearchResult"]


@dataclass(frozen=True)
class JiraSearchResult:
    """Paginated JIRA search results.

    Attributes:
        issues: List of matching JiraIssueDTO instances.
        total: Total number of issues matching the query.
        start_at: Index of the first result returned.
        max_results: Maximum results per page.
    """

    issues: list[JiraIssueDTO]
    total: int
    start_at: int
    max_results: int
