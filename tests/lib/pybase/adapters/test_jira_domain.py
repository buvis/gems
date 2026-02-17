from __future__ import annotations

from datetime import datetime, timezone

from buvis.pybase.adapters.jira.domain.jira_comment_dto import JiraCommentDTO
from buvis.pybase.adapters.jira.domain.jira_issue_dto import JiraIssueDTO
from buvis.pybase.adapters.jira.domain.jira_search_result import JiraSearchResult


def build_issue(key: str) -> JiraIssueDTO:
    """Return a JiraIssueDTO with the required fields populated."""
    return JiraIssueDTO(
        project="PROJ",
        title="Sample Issue",
        description="Sample description",
        issue_type="Task",
        labels=["sample"],
        priority="Medium",
        ticket="PARENT-1",
        feature="EPIC-1",
        assignee="assignee",
        reporter="reporter",
        team="Dev",
        region="US",
        id=key,
        link=f"https://jira.example.com/browse/{key}",
    )


def test_jira_comment_dto_instantiation() -> None:
    """All required fields populated, is_internal defaults to False."""
    now = datetime.now(tz=timezone.utc)
    comment = JiraCommentDTO(
        id="12345",
        author="jsmith",
        body="Example note",
        created=now,
    )

    assert comment.id == "12345"
    assert comment.author == "jsmith"
    assert comment.body == "Example note"
    assert comment.created == now
    assert comment.is_internal is False


def test_jira_search_result_pagination() -> None:
    """JiraSearchResult stores pagination info alongside issues."""
    result = JiraSearchResult(
        issues=[build_issue("PROJ-1")],
        total=5,
        start_at=0,
        max_results=50,
    )

    assert len(result.issues) == 1
    assert result.total == 5
    assert result.start_at == 0
    assert result.max_results == 50
