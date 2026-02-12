"""Tests for Jira adapter exceptions."""

from __future__ import annotations

from buvis.pybase.adapters.jira.exceptions import (
    JiraError,
    JiraLinkError,
    JiraNotFoundError,
    JiraTransitionError,
)


class TestJiraError:
    """Tests for the JiraError base class."""

    def test_raises_from_exception(self) -> None:
        """JiraError inherits from Exception."""
        assert issubclass(JiraError, Exception)

    def test_string_represents_message(self) -> None:
        """JiraError forwards its message to Exception."""
        message = "jira failure"
        exc = JiraError(message)
        assert str(exc) == message


class TestJiraNotFoundError:
    """Tests for JiraNotFoundError."""

    def test_message_contains_issue_key(self) -> None:
        """Exception message includes the missing issue key."""
        issue_key = "ABC-123"
        exc = JiraNotFoundError(issue_key)
        assert str(exc) == f"Issue not found: {issue_key}"
        assert exc.issue_key == issue_key

    def test_is_subclass_of_jira_error(self) -> None:
        """JiraNotFoundError derives from JiraError."""
        assert issubclass(JiraNotFoundError, JiraError)


class TestJiraTransitionError:
    """Tests for JiraTransitionError."""

    def test_message_includes_transition_and_issue(self) -> None:
        """Transition name and issue key appear in the message."""
        issue_key = "ABC-123"
        transition = "Start Progress"
        exc = JiraTransitionError(issue_key, transition)
        assert str(exc) == f"Transition '{transition}' unavailable for {issue_key}"
        assert exc.issue_key == issue_key
        assert exc.transition == transition

    def test_is_subclass_of_jira_error(self) -> None:
        """JiraTransitionError derives from JiraError."""
        assert issubclass(JiraTransitionError, JiraError)


class TestJiraLinkError:
    """Tests for JiraLinkError."""

    def test_message_lists_endpoints(self) -> None:
        """Message shows the from/to keys and link type."""
        from_key = "ABC-123"
        to_key = "DEF-456"
        link_type = "Depends On"
        exc = JiraLinkError(from_key, to_key, link_type)
        assert str(exc) == f"Failed to link {from_key} -> {to_key} ({link_type})"
        assert exc.from_key == from_key
        assert exc.to_key == to_key
        assert exc.link_type == link_type
        assert exc.reason is None

    def test_message_includes_reason_when_provided(self) -> None:
        """Message appends reason when given."""
        from_key = "ABC-123"
        to_key = "DEF-456"
        link_type = "Blocks"
        reason = "Permission denied"
        exc = JiraLinkError(from_key, to_key, link_type, reason=reason)
        assert str(exc) == f"Failed to link {from_key} -> {to_key} ({link_type}): {reason}"
        assert exc.reason == reason

    def test_is_subclass_of_jira_error(self) -> None:
        """JiraLinkError derives from JiraError."""
        assert issubclass(JiraLinkError, JiraError)
