"""JIRA REST API adapter for issue operations.

Provides JiraAdapter for CRUD operations on JIRA issues including:
- Issue creation, retrieval, update
- JQL search with pagination
- Workflow transitions
- Comments (add/retrieve)
- Issue linking

Configuration via JiraSettings pydantic model with env vars.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

try:
    from jira import JIRA
    from jira.exceptions import JIRAError
except ImportError as _exc:
    raise ImportError("bim requires the 'bim' extra. Install with: uv tool install buvis-gems[bim]") from _exc

if TYPE_CHECKING:
    from jira.resources import Issue

from buvis.pybase.adapters.jira.domain import (
    JiraCommentDTO,
    JiraIssueDTO,
    JiraSearchResult,
)
from buvis.pybase.adapters.jira.exceptions import (
    JiraLinkError,
    JiraNotFoundError,
    JiraTransitionError,
)
from buvis.pybase.adapters.jira.settings import JiraSettings


class JiraAdapter:
    """JIRA REST API adapter for issue operations.

    Requirements:
        Provide a populated `JiraSettings` instance with `server` and `token`.

    Optional:
        Configure `proxy` in the settings to route requests through a proxy server.

    Example:
        >>> settings = JiraSettings(server="https://jira", token="abc123")
        >>> jira = JiraAdapter(settings)
        >>> issue = JiraIssueDTO(...)
        >>> created = jira.create(issue)
        >>> print(created.link)
        >>> jira.get(created.id)
        >>> results = jira.search("project = PROJ ORDER BY created DESC", max_results=5)
        >>> jira.transition(created.id, "Start Progress")
    """

    def __init__(self: JiraAdapter, settings: JiraSettings) -> None:
        """Initialize JIRA connection.

        Args:
            settings: JiraSettings instance with server/token values.
        """
        self._settings = settings
        proxies = None
        if self._settings.proxy:
            proxies = {"https": str(self._settings.proxy)}

        jira_kwargs: dict[str, Any] = {
            "server": str(self._settings.server),
            "token_auth": self._settings.token.get_secret_value(),
        }
        if proxies:
            jira_kwargs["proxies"] = proxies

        self._jira = JIRA(**jira_kwargs)

    def create(self, issue: JiraIssueDTO) -> JiraIssueDTO:
        """Create a JIRA issue via the REST API.

        Args:
            issue (JiraIssueDTO): containing all required fields.

        Returns:
            JiraIssueDTO: populated with server-assigned id and link.

        Custom Field Mappings:
            Determined by `self._settings.field_mappings`. Defaults:
            ticket -> customfield_11502, team -> customfield_10501,
            feature -> customfield_10001, region -> customfield_12900.

        Note:
            Custom fields customfield_10001 (feature) and customfield_12900 (region)
            require post-creation update due to JIRA API limitations.
        """
        field_mappings = self._settings.field_mappings

        fields: dict[str, Any] = {
            "assignee": {"key": issue.assignee, "name": issue.assignee},
            field_mappings.feature: issue.feature,
            field_mappings.ticket: issue.ticket,
            "description": issue.description,
            "issuetype": {"name": issue.issue_type},
            "labels": issue.labels,
            "priority": {"name": issue.priority},
            "project": {"key": issue.project},
            "reporter": {"key": issue.reporter, "name": issue.reporter},
            "summary": issue.title,
        }
        fields[field_mappings.environment] = [{"value": "Production"}]
        if issue.team is not None:
            fields[field_mappings.team] = {"value": issue.team}
        if issue.region is not None:
            fields[field_mappings.region] = {"value": issue.region}

        new_issue = self._jira.create_issue(fields=fields)
        # some custom fields aren't populated on issue creation
        # so I have to update them after issue creation
        new_issue = self._jira.issue(new_issue.key)
        new_issue.update(**{field_mappings.feature: issue.feature})  # type: ignore[arg-type]
        if issue.region is not None:
            new_issue.update(**{field_mappings.region: {"value": issue.region}})  # type: ignore[arg-type]

        ticket_value = getattr(new_issue.fields, field_mappings.ticket, None)
        feature_value = getattr(new_issue.fields, field_mappings.feature, None)
        team_field_value = getattr(new_issue.fields, field_mappings.team, None)
        region_field_value = getattr(new_issue.fields, field_mappings.region, None)

        return JiraIssueDTO(
            project=new_issue.fields.project.key,
            title=new_issue.fields.summary,
            description=new_issue.fields.description or "",
            issue_type=new_issue.fields.issuetype.name,
            labels=new_issue.fields.labels or [],
            priority=new_issue.fields.priority.name,
            ticket=str(ticket_value) if ticket_value else "",
            feature=str(feature_value) if feature_value else "",
            assignee=cast(Any, new_issue.fields.assignee).key,
            reporter=cast(Any, new_issue.fields.reporter).key,
            team=getattr(team_field_value, "value", None),
            region=getattr(region_field_value, "value", None),
            id=new_issue.key,
            link=new_issue.permalink(),  # type: ignore[no-untyped-call]
        )

    def _issue_to_dto(self, issue: Issue) -> JiraIssueDTO:
        """Convert JIRA issue object to DTO."""
        fm = self._settings.field_mappings
        team_val = getattr(issue.fields, fm.team, None)
        region_val = getattr(issue.fields, fm.region, None)
        return JiraIssueDTO(
            project=issue.fields.project.key,
            title=issue.fields.summary,
            description=issue.fields.description or "",
            issue_type=issue.fields.issuetype.name,
            labels=issue.fields.labels or [],
            priority=issue.fields.priority.name if issue.fields.priority else "Medium",
            ticket=getattr(issue.fields, fm.ticket, "") or "",
            feature=getattr(issue.fields, fm.feature, "") or "",
            assignee=issue.fields.assignee.key if issue.fields.assignee else "",
            reporter=issue.fields.reporter.key if issue.fields.reporter else "",
            team=getattr(team_val, "value", None) if team_val else None,
            region=getattr(region_val, "value", None) if region_val else None,
            id=issue.key,
            link=issue.permalink(),  # type: ignore[no-untyped-call]
        )

    def get(self, issue_key: str) -> JiraIssueDTO:
        """Retrieve issue by key.

        Args:
            issue_key: JIRA issue key (e.g., "PROJ-123").

        Returns:
            JiraIssueDTO with issue data.

        Raises:
            JiraNotFoundError: Issue does not exist.
        """
        try:
            issue = self._jira.issue(issue_key)
        except JIRAError as error:
            if getattr(error, "status_code", None) == 404:
                raise JiraNotFoundError(issue_key) from error
            raise

        return self._issue_to_dto(issue)

    def search(
        self,
        jql: str,
        start_at: int = 0,
        max_results: int = 50,
        fields: str | None = None,
    ) -> JiraSearchResult:
        """Execute JQL query with pagination.

        Args:
            jql: JQL query string.
            start_at: Index of first result (for pagination).
            max_results: Maximum results to return.
            fields: Comma-separated field names to include, or None for all.

        Returns:
            JiraSearchResult with matching issues and pagination info.
        """
        results = self._jira.search_issues(
            jql,
            startAt=start_at,
            maxResults=max_results,
            fields=fields,
        )
        issues = [self._issue_to_dto(issue) for issue in results]
        return JiraSearchResult(
            issues=issues,
            total=results.total,
            start_at=start_at,
            max_results=max_results,
        )

    def get_link_types(self) -> list[str]:
        """Get available issue link types.

        Returns:
            List of link type names (e.g., "Blocks", "Duplicates").

        Raises:
            JIRAError: JIRA API call failed.
        """
        link_types = self._jira.issue_link_types()
        return [lt.name for lt in link_types]

    def link_issues(
        self,
        from_key: str,
        to_key: str,
        link_type: str,
    ) -> None:
        """Create link between issues.

        Args:
            from_key: Source issue key (outward side of link).
            to_key: Target issue key (inward side of link).
            link_type: Link type name (e.g., "Blocks", "Duplicates").

        Raises:
            JiraNotFoundError: Either issue does not exist.
            JiraLinkError: Link creation failed.
        """
        self.get(from_key)  # validate exists
        self.get(to_key)  # validate exists

        try:
            self._jira.create_issue_link(
                type=link_type,
                inwardIssue=to_key,
                outwardIssue=from_key,
            )
        except JIRAError as e:
            reason = str(e) or None
            raise JiraLinkError(from_key, to_key, link_type, reason=reason) from e

    def update(self, issue_key: str, fields: dict[str, Any]) -> JiraIssueDTO:
        """Update issue fields.

        Args:
            issue_key: Issue to update.
            fields: Dict of field names to new values.

        Returns:
            Updated JiraIssueDTO.

        Raises:
            JiraNotFoundError: Issue does not exist.
        """
        try:
            issue = self._jira.issue(issue_key)
        except JIRAError as error:
            if getattr(error, "status_code", None) == 404:
                raise JiraNotFoundError(issue_key) from error
            raise

        issue.update(fields=fields)

        return self.get(issue_key)

    def add_comment(
        self,
        issue_key: str,
        body: str,
        is_internal: bool = False,
    ) -> JiraCommentDTO:
        """Add comment to issue.

        Args:
            issue_key: JIRA issue key.
            body: Comment text content.
            is_internal: If True, restrict visibility to Administrators.

        Returns:
            JiraCommentDTO for the created comment.

        Raises:
            JiraNotFoundError: Issue does not exist.
        """
        self.get(issue_key)  # validate exists

        visibility = None
        if is_internal:
            visibility = {"type": "role", "value": "Administrators"}

        comment = self._jira.add_comment(issue_key, body, visibility=visibility)

        return JiraCommentDTO(
            id=comment.id,
            author=comment.author.key if comment.author else "",
            body=comment.body or "",
            created=datetime.fromisoformat(comment.created.replace("Z", "+00:00")),
            is_internal=is_internal,
        )

    def get_comments(self, issue_key: str) -> list[JiraCommentDTO]:
        """Get all comments on issue.

        Args:
            issue_key: JIRA issue key.

        Returns:
            List of JiraCommentDTO, chronologically ordered.

        Raises:
            JiraNotFoundError: Issue does not exist.
        """
        self.get(issue_key)  # validate exists

        comments = self._jira.comments(issue_key)

        return [
            JiraCommentDTO(
                id=c.id,
                author=c.author.key if c.author else "",
                body=c.body or "",
                created=datetime.fromisoformat(c.created.replace("Z", "+00:00")),
                is_internal=getattr(c, "visibility", None) is not None,
            )
            for c in comments
        ]

    def get_transitions(self, issue_key: str) -> list[dict[str, str]]:
        """List available transitions for issue.

        Args:
            issue_key: JIRA issue key.

        Returns:
            List of dicts with "id" and "name" keys.

        Raises:
            JiraNotFoundError: Issue does not exist.
        """
        self.get(issue_key)  # validate exists
        transitions = self._jira.transitions(issue_key)
        return [{"id": t["id"], "name": t["name"]} for t in transitions]

    def transition(
        self,
        issue_key: str,
        transition: str,
        fields: dict[str, Any] | None = None,
        comment: str | None = None,
    ) -> None:
        """Execute workflow transition.

        Args:
            issue_key: JIRA issue key.
            transition: Transition ID or name.
            fields: Optional field updates during transition.
            comment: Optional comment to add during transition.

        Raises:
            JiraNotFoundError: Issue does not exist.
            JiraTransitionError: Transition unavailable.
        """
        available = self.get_transitions(issue_key)
        match = next(
            (t for t in available if t["id"] == transition or t["name"] == transition),
            None,
        )
        if not match:
            raise JiraTransitionError(issue_key, transition)

        self._jira.transition_issue(
            issue_key,
            match["id"],
            fields=fields,
            comment=comment,
        )
