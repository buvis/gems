"""Data transfer object for JIRA issue comments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

__all__ = ["JiraCommentDTO"]


@dataclass(frozen=True)
class JiraCommentDTO:
    """DTO for JIRA issue comments.

    Attributes:
        id: JIRA-assigned comment identifier.
        author: JIRA user key of comment author, empty if user deleted.
        body: Comment text content.
        created: Timezone-aware datetime when comment was created.
        is_internal: True if comment has restricted visibility.
    """

    id: str
    author: str
    body: str
    created: datetime
    is_internal: bool = False
