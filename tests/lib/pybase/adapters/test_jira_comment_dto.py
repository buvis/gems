"""Tests for the JIRA comment DTO."""

from __future__ import annotations

from datetime import datetime

from buvis.pybase.adapters.jira.domain.jira_comment_dto import JiraCommentDTO


class TestJiraCommentDTO:
    """Validate the JiraCommentDTO dataclass."""

    def test_populates_all_fields(self) -> None:
        """All fields are assigned from the provided values."""
        created = datetime(2023, 1, 1, 12, 0, 0)
        comment = JiraCommentDTO(
            id="CMT-001",
            author="contributor",
            body="Here is a comment",
            created=created,
            is_internal=True,
        )

        assert comment.id == "CMT-001"
        assert comment.author == "contributor"
        assert comment.body == "Here is a comment"
        assert comment.created is created
        assert comment.is_internal

    def test_is_internal_defaults_to_false(self) -> None:
        """The internal flag defaults to False when omitted."""
        comment = JiraCommentDTO(
            id="CMT-002",
            author="contributor",
            body="Another comment",
            created=datetime(2023, 1, 2, 12, 0, 0),
        )

        assert comment.is_internal is False

    def test_created_accepts_datetime_objects(self) -> None:
        """The created field accepts datetime instances."""
        timestamp = datetime(2023, 1, 3, 12, 0, 0)
        comment = JiraCommentDTO(
            id="CMT-003",
            author="contributor",
            body="Datetime comment",
            created=timestamp,
        )

        assert comment.created is timestamp
