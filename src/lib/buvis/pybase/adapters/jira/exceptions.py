"""Jira adapter-specific exceptions."""

from __future__ import annotations

__all__ = [
    "JiraError",
    "JiraLinkError",
    "JiraNotFoundError",
    "JiraTransitionError",
]


class JiraError(Exception):
    """Base exception for the Jira adapter."""


class JiraNotFoundError(JiraError):
    """Raised when a Jira issue cannot be located."""

    def __init__(self, issue_key: str) -> None:
        self.issue_key = issue_key
        super().__init__(f"Issue not found: {issue_key}")


class JiraTransitionError(JiraError):
    """Raised when a transition is unavailable for an issue."""

    def __init__(self, issue_key: str, transition: str) -> None:
        self.issue_key = issue_key
        self.transition = transition
        super().__init__(f"Transition '{transition}' unavailable for {issue_key}")


class JiraLinkError(JiraError):
    """Raised when linking two Jira issues fails."""

    def __init__(
        self,
        from_key: str,
        to_key: str,
        link_type: str,
        reason: str | None = None,
    ) -> None:
        self.from_key = from_key
        self.to_key = to_key
        self.link_type = link_type
        self.reason = reason
        msg = f"Failed to link {from_key} -> {to_key} ({link_type})"
        if reason:
            msg = f"{msg}: {reason}"
        super().__init__(msg)
