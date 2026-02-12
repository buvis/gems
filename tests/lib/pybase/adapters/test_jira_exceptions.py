"""Tests for Jira adapter exceptions."""

from __future__ import annotations

import pytest
from buvis.pybase.adapters.jira.exceptions import (
    JiraError,
    JiraLinkError,
    JiraNotFoundError,
    JiraTransitionError,
)


class TestJiraError:
    def test_raises_from_exception(self) -> None:
        assert issubclass(JiraError, Exception)

    def test_string_represents_message(self) -> None:
        exc = JiraError("jira failure")
        assert str(exc) == "jira failure"


class TestJiraNotFoundError:
    def test_message_contains_issue_key(self) -> None:
        exc = JiraNotFoundError("ABC-123")
        assert str(exc) == "Issue not found: ABC-123"
        assert exc.issue_key == "ABC-123"


class TestJiraTransitionError:
    def test_message_includes_transition_and_issue(self) -> None:
        exc = JiraTransitionError("ABC-123", "Start Progress")
        assert str(exc) == "Transition 'Start Progress' unavailable for ABC-123"
        assert exc.issue_key == "ABC-123"
        assert exc.transition == "Start Progress"


class TestJiraLinkError:
    def test_message_lists_endpoints(self) -> None:
        exc = JiraLinkError("ABC-123", "DEF-456", "Depends On")
        assert str(exc) == "Failed to link ABC-123 -> DEF-456 (Depends On)"
        assert exc.reason is None

    def test_message_includes_reason_when_provided(self) -> None:
        exc = JiraLinkError("ABC-123", "DEF-456", "Blocks", reason="Permission denied")
        assert str(exc) == "Failed to link ABC-123 -> DEF-456 (Blocks): Permission denied"
        assert exc.reason == "Permission denied"


@pytest.mark.parametrize(
    "cls",
    [JiraNotFoundError, JiraTransitionError, JiraLinkError],
)
def test_subclass_of_jira_error(cls: type) -> None:
    assert issubclass(cls, JiraError)
