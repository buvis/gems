"""Tests for JiraSearchResult dataclass."""

from __future__ import annotations

from buvis.pybase.adapters.jira.domain.jira_issue_dto import JiraIssueDTO
from buvis.pybase.adapters.jira.domain.jira_search_result import JiraSearchResult


class TestJiraSearchResult:
    """Validate the JiraSearchResult dataclass behavior."""

    def test_initializes_with_all_fields(self) -> None:
        """All properties retain the provided values."""
        issue = JiraIssueDTO(
            project="BUV",
            title="Example issue",
            description="description",
            issue_type="Task",
            labels=["release"],
            priority="Medium",
            ticket="BUV-123",
            feature="feature-1",
            assignee="alice",
            reporter="bob",
            team="platform",
            region="emea",
            id="BUV-001",
            link="https://example.com/BUV-001",
        )
        result = JiraSearchResult(
            issues=[issue],
            total=1,
            start_at=0,
            max_results=50,
        )

        assert result.issues == [issue]
        assert result.total == 1
        assert result.start_at == 0
        assert result.max_results == 50

    def test_accepts_issue_list(self) -> None:
        """The issues field accepts multiple JiraIssueDTO instances."""
        first = JiraIssueDTO(
            project="BUV",
            title="First issue",
            description="first",
            issue_type="Task",
            labels=[],
            priority="Low",
            ticket="BUV-124",
            feature="feature-2",
            assignee="alice",
            reporter="alice",
            team="platform",
            region="apac",
        )
        second = JiraIssueDTO(
            project="BUV",
            title="Second issue",
            description="second",
            issue_type="Bug",
            labels=["urgent"],
            priority="High",
            ticket="BUV-125",
            feature="feature-3",
            assignee="bob",
            reporter="alice",
            team="platform",
            region="emea",
        )
        result = JiraSearchResult(
            issues=[first, second],
            total=2,
            start_at=10,
            max_results=25,
        )

        assert result.issues == [first, second]
        assert result.total == 2
        assert result.start_at == 10
        assert result.max_results == 25

    def test_empty_issues_list_allows_zero_total(self) -> None:
        """An empty issues list is valid when there are no search matches."""
        result = JiraSearchResult(
            issues=[],
            total=0,
            start_at=0,
            max_results=50,
        )

        assert result.issues == []
        assert result.total == 0
        assert result.start_at == 0
        assert result.max_results == 50
