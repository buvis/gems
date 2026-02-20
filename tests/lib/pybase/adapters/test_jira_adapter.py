from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from buvis.pybase.adapters.jira.domain import JiraCommentDTO, JiraIssueDTO
from buvis.pybase.adapters.jira.exceptions import (
    JiraLinkError,
    JiraNotFoundError,
    JiraTransitionError,
)
from buvis.pybase.adapters.jira.jira import JiraAdapter
from buvis.pybase.adapters.jira.settings import JiraFieldMappings, JiraSettings
from jira.exceptions import JIRAError


@pytest.fixture
def jira_settings(monkeypatch: pytest.MonkeyPatch) -> JiraSettings:
    """Create JiraSettings instance sourced from environment variables."""
    monkeypatch.setenv("BUVIS_JIRA_SERVER", "https://jira.example.com")
    monkeypatch.setenv("BUVIS_JIRA_TOKEN", "test-token")
    return JiraSettings()


@pytest.fixture
def sample_issue_dto() -> JiraIssueDTO:
    """Create a sample JiraIssueDTO for testing."""
    return JiraIssueDTO(
        project="PROJ",
        title="Test Issue",
        description="Test description",
        issue_type="Task",
        labels=["test", "automated"],
        priority="Medium",
        ticket="PARENT-123",
        feature="EPIC-456",
        assignee="testuser",
        reporter="reporter",
        team="DevTeam",
        region="US",
    )


class TestJiraAdapterInit:
    """Test JiraAdapter initialization."""

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_creates_client_with_server_and_token(self, mock_jira: MagicMock, jira_settings: JiraSettings) -> None:
        """Valid settings create a JIRA client."""
        JiraAdapter(jira_settings)

        mock_jira.assert_called_once_with(
            server="https://jira.example.com",
            token_auth="test-token",
        )

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_sets_proxy_when_configured(self, mock_jira: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Proxy config passes proxies dict to JIRA constructor."""
        monkeypatch.setenv("BUVIS_JIRA_SERVER", "https://jira.example.com")
        monkeypatch.setenv("BUVIS_JIRA_TOKEN", "test-token")
        monkeypatch.setenv("BUVIS_JIRA_PROXY", "http://proxy.example.com:8080")

        JiraAdapter(JiraSettings())

        _, kwargs = mock_jira.call_args
        assert kwargs["proxies"] == {"https": "http://proxy.example.com:8080"}

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_multiple_adapters_with_different_proxies(self, mock_jira: MagicMock) -> None:
        """Multiple adapters with different proxies don't conflict."""
        proxy1 = "http://proxy-one.example.com:8080"
        proxy2 = "http://proxy-two.example.com:8080"

        JiraAdapter(
            JiraSettings(
                server="https://jira.example.com",
                token="token-one",
                proxy=proxy1,
            )
        )
        JiraAdapter(
            JiraSettings(
                server="https://jira.example.com",
                token="token-two",
                proxy=proxy2,
            )
        )

        assert mock_jira.call_count == 2
        _, first_kwargs = mock_jira.call_args_list[0]
        _, second_kwargs = mock_jira.call_args_list[1]
        assert first_kwargs["proxies"] == {"https": proxy1}
        assert second_kwargs["proxies"] == {"https": proxy2}


class TestJiraAdapterCreate:
    """Test JiraAdapter.create() method."""

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_creates_issue_with_correct_fields(
        self,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
        sample_issue_dto: JiraIssueDTO,
    ) -> None:
        """create() passes correct field mapping to JIRA API."""
        mock_jira = mock_jira_cls.return_value
        mock_issue = MagicMock()
        mock_issue.key = "PROJ-123"
        mock_issue.permalink.return_value = "https://jira.example.com/browse/PROJ-123"
        mock_issue.fields.project.key = "PROJ"
        mock_issue.fields.summary = "Test Issue"
        mock_issue.fields.description = "Test description"
        mock_issue.fields.issuetype.name = "Task"
        mock_issue.fields.labels = ["test", "automated"]
        mock_issue.fields.priority.name = "Medium"
        mock_issue.fields.customfield_11502 = "PARENT-123"
        mock_issue.fields.customfield_10001 = "EPIC-456"
        mock_issue.fields.assignee.key = "testuser"
        mock_issue.fields.reporter.key = "reporter"
        mock_issue.fields.customfield_10501.value = "DevTeam"
        mock_issue.fields.customfield_12900.value = "US"
        mock_jira.create_issue.return_value = mock_issue
        mock_jira.issue.return_value = mock_issue

        adapter = JiraAdapter(jira_settings)
        adapter.create(sample_issue_dto)

        mock_jira.create_issue.assert_called_once()
        call_fields = mock_jira.create_issue.call_args[1]["fields"]
        assert call_fields["project"] == {"key": "PROJ"}
        assert call_fields["summary"] == "Test Issue"
        assert call_fields["assignee"] == {"key": "testuser", "name": "testuser"}
        field_mappings = jira_settings.field_mappings
        assert call_fields[field_mappings.team] == {"value": "DevTeam"}
        assert call_fields[field_mappings.environment] == [{"value": "Production"}]

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_returns_dto_with_id_and_link(
        self,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
        sample_issue_dto: JiraIssueDTO,
    ) -> None:
        """create() returns DTO with id and link populated."""
        mock_jira = mock_jira_cls.return_value
        mock_issue = MagicMock()
        mock_issue.key = "PROJ-999"
        mock_issue.permalink.return_value = "https://jira.example.com/browse/PROJ-999"
        mock_issue.fields.project.key = "PROJ"
        mock_issue.fields.summary = "Test Issue"
        mock_issue.fields.description = "Test description"
        mock_issue.fields.issuetype.name = "Task"
        mock_issue.fields.labels = ["test", "automated"]
        mock_issue.fields.priority.name = "Medium"
        mock_issue.fields.customfield_11502 = "PARENT-123"
        mock_issue.fields.customfield_10001 = "EPIC-456"
        mock_issue.fields.assignee.key = "testuser"
        mock_issue.fields.reporter.key = "reporter"
        mock_issue.fields.customfield_10501.value = "DevTeam"
        mock_issue.fields.customfield_12900.value = "US"
        mock_jira.create_issue.return_value = mock_issue
        mock_jira.issue.return_value = mock_issue

        adapter = JiraAdapter(jira_settings)
        result = adapter.create(sample_issue_dto)

        assert result.id == "PROJ-999"
        assert result.link == "https://jira.example.com/browse/PROJ-999"
        assert isinstance(result, JiraIssueDTO)

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_updates_custom_fields_after_creation(
        self,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
        sample_issue_dto: JiraIssueDTO,
    ) -> None:
        """create() updates custom fields that require post-creation update."""
        mock_jira = mock_jira_cls.return_value
        mock_created_issue = MagicMock()
        mock_created_issue.key = "PROJ-123"
        mock_fetched_issue = MagicMock()
        mock_fetched_issue.key = "PROJ-123"
        mock_fetched_issue.permalink.return_value = "https://jira.example.com/browse/PROJ-123"
        mock_fetched_issue.fields.project.key = "PROJ"
        mock_fetched_issue.fields.summary = "Test Issue"
        mock_fetched_issue.fields.description = "Test description"
        mock_fetched_issue.fields.issuetype.name = "Task"
        mock_fetched_issue.fields.labels = ["test", "automated"]
        mock_fetched_issue.fields.priority.name = "Medium"
        mock_fetched_issue.fields.customfield_11502 = "PARENT-123"
        mock_fetched_issue.fields.customfield_10001 = "EPIC-456"
        mock_fetched_issue.fields.assignee.key = "testuser"
        mock_fetched_issue.fields.reporter.key = "reporter"
        mock_fetched_issue.fields.customfield_10501.value = "DevTeam"
        mock_fetched_issue.fields.customfield_12900.value = "US"
        mock_jira.create_issue.return_value = mock_created_issue
        mock_jira.issue.return_value = mock_fetched_issue

        adapter = JiraAdapter(jira_settings)
        adapter.create(sample_issue_dto)

        mock_jira.issue.assert_called_once_with("PROJ-123")
        assert mock_fetched_issue.update.call_count == 2
        field_mappings = jira_settings.field_mappings
        mock_fetched_issue.update.assert_any_call(**{field_mappings.feature: "EPIC-456"})
        mock_fetched_issue.update.assert_any_call(**{field_mappings.region: {"value": "US"}})

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_create_omits_team_field_when_none(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """create() does not send team field when issue.team is None."""
        mock_jira = mock_jira_cls.return_value
        mock_issue = MagicMock()
        mock_issue.key = "PROJ-123"
        mock_issue.permalink.return_value = "https://jira.example.com/browse/PROJ-123"
        mock_issue.fields.project.key = "PROJ"
        mock_issue.fields.summary = "Test Issue"
        mock_issue.fields.description = "Test description"
        mock_issue.fields.issuetype.name = "Task"
        mock_issue.fields.labels = ["test"]
        mock_issue.fields.priority.name = "Medium"
        mock_issue.fields.customfield_11502 = "PARENT-123"
        mock_issue.fields.customfield_10001 = "EPIC-456"
        mock_issue.fields.assignee.key = "testuser"
        mock_issue.fields.reporter.key = "reporter"
        mock_issue.fields.customfield_10501 = None
        mock_issue.fields.customfield_12900.value = "US"
        mock_jira.create_issue.return_value = mock_issue
        mock_jira.issue.return_value = mock_issue

        issue_dto = JiraIssueDTO(
            project="PROJ",
            title="Test Issue",
            description="Test description",
            issue_type="Task",
            labels=["test"],
            priority="Medium",
            ticket="PARENT-123",
            feature="EPIC-456",
            assignee="testuser",
            reporter="reporter",
            team=None,
            region="US",
        )

        adapter = JiraAdapter(jira_settings)
        adapter.create(issue_dto)

        call_fields = mock_jira.create_issue.call_args[1]["fields"]
        field_mappings = jira_settings.field_mappings
        assert field_mappings.team not in call_fields

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_create_omits_region_field_when_none(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """create() does not send region field when issue.region is None."""
        mock_jira = mock_jira_cls.return_value
        mock_issue = MagicMock()
        mock_issue.key = "PROJ-123"
        mock_issue.permalink.return_value = "https://jira.example.com/browse/PROJ-123"
        mock_issue.fields.project.key = "PROJ"
        mock_issue.fields.summary = "Test Issue"
        mock_issue.fields.description = "Test description"
        mock_issue.fields.issuetype.name = "Task"
        mock_issue.fields.labels = ["test"]
        mock_issue.fields.priority.name = "Medium"
        mock_issue.fields.customfield_11502 = "PARENT-123"
        mock_issue.fields.customfield_10001 = "EPIC-456"
        mock_issue.fields.assignee.key = "testuser"
        mock_issue.fields.reporter.key = "reporter"
        mock_issue.fields.customfield_10501.value = "DevTeam"
        mock_issue.fields.customfield_12900 = None
        mock_jira.create_issue.return_value = mock_issue
        mock_jira.issue.return_value = mock_issue

        issue_dto = JiraIssueDTO(
            project="PROJ",
            title="Test Issue",
            description="Test description",
            issue_type="Task",
            labels=["test"],
            priority="Medium",
            ticket="PARENT-123",
            feature="EPIC-456",
            assignee="testuser",
            reporter="reporter",
            team="DevTeam",
            region=None,
        )

        adapter = JiraAdapter(jira_settings)
        adapter.create(issue_dto)

        call_fields = mock_jira.create_issue.call_args[1]["fields"]
        field_mappings = jira_settings.field_mappings
        assert field_mappings.region not in call_fields
        # Only feature update should happen, not region
        assert mock_issue.update.call_count == 1
        mock_issue.update.assert_called_with(**{field_mappings.feature: "EPIC-456"})


class TestJiraAdapterGet:
    """Test JiraAdapter.get() method."""

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_returns_dto_for_valid_key(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """get() returns a populated DTO when Jira returns an issue."""
        mock_jira = mock_jira_cls.return_value
        mock_issue = MagicMock()
        mock_issue.key = "PROJ-1"
        mock_issue.permalink.return_value = "https://jira.example.com/browse/PROJ-1"
        mock_issue.fields.project.key = "PROJ"
        mock_issue.fields.summary = "Loaded issue"
        mock_issue.fields.description = "Loaded description"
        mock_issue.fields.issuetype.name = "Task"
        mock_issue.fields.labels = ["loaded"]
        priority_field = MagicMock()
        priority_field.name = "High"
        mock_issue.fields.priority = priority_field
        mock_issue.fields.customfield_11502 = "PARENT-123"
        mock_issue.fields.customfield_10001 = "EPIC-456"
        mock_issue.fields.assignee.key = "testuser"
        mock_issue.fields.reporter.key = "reporter"
        mock_issue.fields.customfield_10501.value = "DevTeam"
        mock_issue.fields.customfield_12900.value = "US"
        mock_jira.issue.return_value = mock_issue

        adapter = JiraAdapter(jira_settings)
        result = adapter.get("PROJ-1")

        assert isinstance(result, JiraIssueDTO)
        assert result.id == "PROJ-1"
        assert result.link == "https://jira.example.com/browse/PROJ-1"
        assert result.ticket == "PARENT-123"
        assert result.feature == "EPIC-456"
        assert result.team == "DevTeam"
        assert result.region == "US"

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_raises_not_found_for_404(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """A 404 from Jira is wrapped in JiraNotFoundError."""
        mock_jira = mock_jira_cls.return_value
        error = JIRAError("not found")
        error.status_code = 404
        mock_jira.issue.side_effect = error

        adapter = JiraAdapter(jira_settings)
        with pytest.raises(JiraNotFoundError):
            adapter.get("PROJ-404")

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_propagates_other_jira_errors(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """Non-404 errors bubble up unchanged."""
        mock_jira = mock_jira_cls.return_value
        error = JIRAError("server error")
        error.status_code = 500
        mock_jira.issue.side_effect = error

        adapter = JiraAdapter(jira_settings)
        with pytest.raises(JIRAError):
            adapter.get("PROJ-500")

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_uses_field_mappings_from_settings(self, mock_jira_cls: MagicMock) -> None:
        """Custom field mappings are respected when reading Jira fields."""
        mock_jira = mock_jira_cls.return_value
        custom_field_mappings = JiraFieldMappings(
            ticket="custom_ticket",
            feature="custom_feature",
            team="custom_team",
            region="custom_region",
        )
        settings = JiraSettings(
            server="https://jira.example.com",
            token="test-token",
            field_mappings=custom_field_mappings,
        )
        mock_issue = MagicMock()
        mock_issue.key = "PROJ-2"
        mock_issue.permalink.return_value = "https://jira.example.com/browse/PROJ-2"
        mock_issue.fields.project.key = "PROJ"
        mock_issue.fields.summary = "Custom mapping issue"
        mock_issue.fields.description = "Custom description"
        mock_issue.fields.issuetype.name = "Bug"
        mock_issue.fields.labels = []
        priority_field = MagicMock()
        priority_field.name = "Medium"
        mock_issue.fields.priority = priority_field
        setattr(mock_issue.fields, "custom_ticket", "CUSTOM-123")
        setattr(mock_issue.fields, "custom_feature", "FEATURE-123")
        team_field = MagicMock()
        team_field.value = "CustomTeam"
        setattr(mock_issue.fields, "custom_team", team_field)
        region_field = MagicMock()
        region_field.value = "CustomRegion"
        setattr(mock_issue.fields, "custom_region", region_field)
        mock_issue.fields.assignee.key = "assignee"
        mock_issue.fields.reporter.key = "reporter"
        mock_jira.issue.return_value = mock_issue

        adapter = JiraAdapter(settings)
        result = adapter.get("PROJ-2")

        assert result.ticket == "CUSTOM-123"
        assert result.feature == "FEATURE-123"
        assert result.team == "CustomTeam"
        assert result.region == "CustomRegion"


class TestJiraAdapterUpdate:
    """Test JiraAdapter.update() method."""

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_calls_update_with_fields(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """update() forwards provided fields to JIRA."""
        mock_jira = mock_jira_cls.return_value
        mock_issue = MagicMock()
        mock_jira.issue.return_value = mock_issue

        updated_dto = JiraIssueDTO(
            project="PROJ",
            title="Updated",
            description="desc",
            issue_type="Task",
            labels=[],
            priority="Medium",
            ticket="PARENT-1",
            feature="EPIC-1",
            assignee="user",
            reporter="reporter",
            team="Team",
            region="US",
        )
        fields = {"summary": "Updated"}

        with patch.object(JiraAdapter, "get", return_value=updated_dto) as mock_get:
            adapter = JiraAdapter(jira_settings)
            adapter.update("PROJ-1", fields)

        mock_jira.issue.assert_called_once_with("PROJ-1")
        mock_issue.update.assert_called_once_with(fields=fields)
        mock_get.assert_called_once_with("PROJ-1")

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_returns_refreshed_dto(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """update() returns the DTO from the final get()."""
        mock_jira = mock_jira_cls.return_value
        mock_issue = MagicMock()
        mock_jira.issue.return_value = mock_issue

        refreshed_dto = JiraIssueDTO(
            project="PROJ",
            title="Refreshed",
            description="desc",
            issue_type="Task",
            labels=[],
            priority="Medium",
            ticket="PARENT-1",
            feature="EPIC-1",
            assignee="user",
            reporter="reporter",
            team="Team",
            region="US",
        )

        with patch.object(JiraAdapter, "get", return_value=refreshed_dto):
            adapter = JiraAdapter(jira_settings)
            result = adapter.update("PROJ-1", {"summary": "Refreshed"})

        assert result is refreshed_dto

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_raises_not_found_for_missing_issue(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """update() surfaces JiraNotFoundError when issue can't be found."""
        mock_jira = mock_jira_cls.return_value
        error = JIRAError("not found")
        error.status_code = 404
        mock_jira.issue.side_effect = error

        adapter = JiraAdapter(jira_settings)

        with pytest.raises(JiraNotFoundError):
            adapter.update("PROJ-404", {"summary": "Missing"})


class TestJiraAdapterSearch:
    """Test JiraAdapter.search() pagination helper."""

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_returns_search_result_with_issues(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """Search returns DTOs for each matching issue."""
        mock_jira = mock_jira_cls.return_value
        mock_issue = MagicMock()
        mock_issue.key = "PROJ-1"
        mock_issue.permalink.return_value = "https://jira.example.com/browse/PROJ-1"
        mock_issue.fields.project.key = "PROJ"
        mock_issue.fields.summary = "Search result"
        mock_issue.fields.description = "Search description"
        mock_issue.fields.issuetype.name = "Task"
        mock_issue.fields.labels = ["search"]
        priority_field = MagicMock()
        priority_field.name = "High"
        mock_issue.fields.priority = priority_field
        mock_issue.fields.assignee.key = "searcher"
        mock_issue.fields.reporter.key = "reporter"
        field_mappings = jira_settings.field_mappings
        setattr(mock_issue.fields, field_mappings.ticket, "PARENT-123")
        setattr(mock_issue.fields, field_mappings.feature, "EPIC-456")
        team_field = MagicMock()
        team_field.value = "SearchTeam"
        setattr(mock_issue.fields, field_mappings.team, team_field)
        region_field = MagicMock()
        region_field.value = "EU"
        setattr(mock_issue.fields, field_mappings.region, region_field)

        results = MagicMock()
        results.__iter__.return_value = iter([mock_issue])
        results.total = 1
        mock_jira.search_issues.return_value = results

        adapter = JiraAdapter(jira_settings)
        result = adapter.search("project = PROJ")

        assert result.total == 1
        assert result.start_at == 0
        assert result.max_results == 50
        assert len(result.issues) == 1
        issue_dto = result.issues[0]
        assert issue_dto.id == "PROJ-1"
        assert issue_dto.team == "SearchTeam"
        assert issue_dto.region == "EU"

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_returns_empty_results(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """Empty search results still return a JiraSearchResult instance."""
        mock_jira = mock_jira_cls.return_value
        results = MagicMock()
        results.__iter__.return_value = iter([])
        results.total = 0
        mock_jira.search_issues.return_value = results

        adapter = JiraAdapter(jira_settings)
        result = adapter.search("project = PROJ")

        assert result.total == 0
        assert result.issues == []

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_passes_pagination_params(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """start_at/max_results propagate to the underlying adapter."""
        mock_jira = mock_jira_cls.return_value
        results = MagicMock()
        results.__iter__.return_value = iter([])
        results.total = 0
        mock_jira.search_issues.return_value = results

        adapter = JiraAdapter(jira_settings)
        result = adapter.search("project = PROJ", start_at=5, max_results=25)

        mock_jira.search_issues.assert_called_once_with("project = PROJ", startAt=5, maxResults=25, fields=None)
        assert result.start_at == 5
        assert result.max_results == 25

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_passes_fields_filter(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """fields argument is forwarded to JIRA."""
        mock_jira = mock_jira_cls.return_value
        results = MagicMock()
        results.__iter__.return_value = iter([])
        results.total = 0
        mock_jira.search_issues.return_value = results

        adapter = JiraAdapter(jira_settings)
        adapter.search("project = PROJ", fields="summary,labels")

        mock_jira.search_issues.assert_called_once_with(
            "project = PROJ", startAt=0, maxResults=50, fields="summary,labels"
        )


class TestJiraAdapterTransitions:
    """Test transition helpers on JiraAdapter."""

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_get_transitions_returns_list(
        self,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
        sample_issue_dto: JiraIssueDTO,
    ) -> None:
        """Transitions are groomed to id/name pairs."""
        mock_jira = mock_jira_cls.return_value
        mock_jira.transitions.return_value = [
            {"id": "1", "name": "Start Progress"},
            {"id": "2", "name": "Done"},
        ]

        with patch.object(JiraAdapter, "get", return_value=sample_issue_dto) as mock_get:
            adapter = JiraAdapter(jira_settings)
            result = adapter.get_transitions("PROJ-1")

        assert result == [
            {"id": "1", "name": "Start Progress"},
            {"id": "2", "name": "Done"},
        ]
        mock_jira.transitions.assert_called_once_with("PROJ-1")
        mock_get.assert_called_once_with("PROJ-1")

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_get_transitions_raises_not_found(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """Missing issues propagate JiraNotFoundError."""
        mock_jira = mock_jira_cls.return_value
        with patch.object(JiraAdapter, "get", side_effect=JiraNotFoundError("PROJ-404")) as mock_get:
            adapter = JiraAdapter(jira_settings)
            with pytest.raises(JiraNotFoundError):
                adapter.get_transitions("PROJ-404")

        mock_jira.transitions.assert_not_called()
        mock_get.assert_called_once_with("PROJ-404")

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_transition_executes_by_name(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """Transitions can be triggered by name."""
        mock_jira = mock_jira_cls.return_value
        transitions = [{"id": "1", "name": "In Progress"}]

        with patch.object(JiraAdapter, "get_transitions", return_value=transitions) as mock_get_transitions:
            adapter = JiraAdapter(jira_settings)
            adapter.transition("PROJ-1", "In Progress")

        mock_get_transitions.assert_called_once_with("PROJ-1")
        mock_jira.transition_issue.assert_called_once_with(
            "PROJ-1",
            "1",
            fields=None,
            comment=None,
        )

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_transition_executes_by_id(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """Transitions can be triggered by id."""
        mock_jira = mock_jira_cls.return_value
        transitions = [{"id": "42", "name": "Done"}]

        with patch.object(JiraAdapter, "get_transitions", return_value=transitions) as mock_get_transitions:
            adapter = JiraAdapter(jira_settings)
            adapter.transition("PROJ-1", "42")

        mock_get_transitions.assert_called_once_with("PROJ-1")
        mock_jira.transition_issue.assert_called_once_with(
            "PROJ-1",
            "42",
            fields=None,
            comment=None,
        )

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_transition_raises_when_unavailable(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """Unavailable transitions raise JiraTransitionError."""
        mock_jira = mock_jira_cls.return_value
        transitions = [{"id": "7", "name": "Start"}]

        with patch.object(JiraAdapter, "get_transitions", return_value=transitions) as mock_get_transitions:
            adapter = JiraAdapter(jira_settings)
            with pytest.raises(JiraTransitionError):
                adapter.transition("PROJ-1", "Close")

        mock_get_transitions.assert_called_once_with("PROJ-1")
        mock_jira.transition_issue.assert_not_called()

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_transition_passes_fields_and_comment(self, mock_jira_cls: MagicMock, jira_settings: JiraSettings) -> None:
        """Fields and comments are forwarded to JIRA transitions."""
        mock_jira = mock_jira_cls.return_value
        transitions = [{"id": "123", "name": "Review"}]
        fields = {"resolution": {"name": "Done"}}
        comment = "moving to review"

        with patch.object(JiraAdapter, "get_transitions", return_value=transitions) as mock_get_transitions:
            adapter = JiraAdapter(jira_settings)
            adapter.transition("PROJ-1", "Review", fields=fields, comment=comment)

        mock_get_transitions.assert_called_once_with("PROJ-1")
        mock_jira.transition_issue.assert_called_once_with(
            "PROJ-1",
            "123",
            fields=fields,
            comment=comment,
        )


class TestJiraAdapterLinks:
    """Test JiraAdapter link type helpers."""

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_get_link_types_returns_list(
        self,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """get_link_types() always returns a list."""
        mock_jira = mock_jira_cls.return_value
        mock_jira.issue_link_types.return_value = []

        adapter = JiraAdapter(jira_settings)
        result = adapter.get_link_types()

        mock_jira.issue_link_types.assert_called_once()
        assert isinstance(result, list)
        assert result == []

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    def test_get_link_types_returns_names(
        self,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """get_link_types() maps objects to their names."""
        mock_jira = mock_jira_cls.return_value
        first = MagicMock()
        first.name = "Blocks"
        second = MagicMock()
        second.name = "Duplicates"
        mock_jira.issue_link_types.return_value = [first, second]

        adapter = JiraAdapter(jira_settings)
        result = adapter.get_link_types()

        assert result == ["Blocks", "Duplicates"]

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(JiraAdapter, "get")
    def test_link_issues_calls_api(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """link_issues() validates issues and creates link."""
        mock_jira = mock_jira_cls.return_value
        mock_get.return_value = MagicMock()

        adapter = JiraAdapter(jira_settings)
        adapter.link_issues("PROJ-1", "PROJ-2", "Blocks")

        mock_get.assert_has_calls([call("PROJ-1"), call("PROJ-2")])
        mock_jira.create_issue_link.assert_called_once_with(
            type="Blocks",
            inwardIssue="PROJ-2",
            outwardIssue="PROJ-1",
        )

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(JiraAdapter, "get")
    def test_link_issues_raises_not_found_for_from_key(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """Missing from_key raises JiraNotFoundError and aborts linking."""
        mock_jira = mock_jira_cls.return_value
        mock_get.side_effect = JiraNotFoundError("PROJ-1")

        adapter = JiraAdapter(jira_settings)

        with pytest.raises(JiraNotFoundError):
            adapter.link_issues("PROJ-1", "PROJ-2", "Depends On")

        mock_jira.create_issue_link.assert_not_called()

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(JiraAdapter, "get")
    def test_link_issues_raises_not_found_for_to_key(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """Missing to_key raises JiraNotFoundError and aborts linking."""
        mock_jira = mock_jira_cls.return_value
        mock_get.side_effect = [
            MagicMock(),
            JiraNotFoundError("PROJ-2"),
        ]

        adapter = JiraAdapter(jira_settings)

        with pytest.raises(JiraNotFoundError):
            adapter.link_issues("PROJ-1", "PROJ-2", "Depends On")

        mock_jira.create_issue_link.assert_not_called()

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(JiraAdapter, "get")
    def test_link_issues_raises_link_error_on_failure(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """JIRAError during link raises JiraLinkError."""
        mock_jira = mock_jira_cls.return_value
        mock_get.return_value = MagicMock()
        mock_jira.create_issue_link.side_effect = JIRAError("boom")

        adapter = JiraAdapter(jira_settings)

        with pytest.raises(JiraLinkError):
            adapter.link_issues("PROJ-1", "PROJ-2", "Blocks")


class TestJiraAdapterComments:
    """Test JiraAdapter.add_comment() helpers."""

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(JiraAdapter, "get")
    def test_add_comment_creates_and_returns_dto(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """add_comment() returns populated JiraCommentDTO."""
        mock_get.return_value = MagicMock()
        mock_jira = mock_jira_cls.return_value
        mock_comment = MagicMock()
        mock_comment.id = "C-1"
        mock_comment.body = "Test comment"
        author_mock = MagicMock()
        author_mock.key = "reporter"
        mock_comment.author = author_mock
        mock_comment.created = "2023-01-02T03:04:05.678Z"
        mock_jira.add_comment.return_value = mock_comment

        adapter = JiraAdapter(jira_settings)
        result = adapter.add_comment("PROJ-1", "Test comment")

        mock_jira.add_comment.assert_called_once_with("PROJ-1", "Test comment", visibility=None)
        assert isinstance(result, JiraCommentDTO)
        assert result.id == "C-1"
        assert result.author == "reporter"
        assert result.body == "Test comment"
        assert result.is_internal is False

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(JiraAdapter, "get")
    def test_add_comment_with_internal_sets_visibility(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """Internal comments request admin visibility."""
        mock_get.return_value = MagicMock()
        mock_jira = mock_jira_cls.return_value
        mock_comment = MagicMock()
        mock_comment.id = "C-2"
        mock_comment.body = "Internal note"
        author_mock = MagicMock()
        author_mock.key = "internal-user"
        mock_comment.author = author_mock
        mock_comment.created = "2023-01-02T00:00:00.000Z"
        mock_jira.add_comment.return_value = mock_comment

        adapter = JiraAdapter(jira_settings)
        result = adapter.add_comment("PROJ-2", "Internal note", is_internal=True)

        mock_jira.add_comment.assert_called_once_with(
            "PROJ-2",
            "Internal note",
            visibility={"type": "role", "value": "Administrators"},
        )
        assert result.is_internal is True

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(
        JiraAdapter,
        "get",
        side_effect=JiraNotFoundError("PROJ-404"),
    )
    def test_add_comment_raises_not_found(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """add_comment() surfaces JiraNotFoundError when issue missing."""
        adapter = JiraAdapter(jira_settings)

        with pytest.raises(JiraNotFoundError):
            adapter.add_comment("PROJ-404", "Missing")

        mock_jira_cls.return_value.add_comment.assert_not_called()
        mock_get.assert_called_once_with("PROJ-404")

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(JiraAdapter, "get")
    def test_datetime_parsing_handles_jira_format(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """Timestamps containing Z parse successfully."""
        mock_get.return_value = MagicMock()
        mock_jira = mock_jira_cls.return_value
        mock_comment = MagicMock()
        mock_comment.id = "C-3"
        mock_comment.body = "Timestamp test"
        author_mock = MagicMock()
        author_mock.key = "tester"
        mock_comment.author = author_mock
        mock_comment.created = "2023-01-02T03:04:05.678Z"
        mock_jira.add_comment.return_value = mock_comment

        adapter = JiraAdapter(jira_settings)
        result = adapter.add_comment("PROJ-3", "Timestamp test")

        assert result.created.isoformat() == "2023-01-02T03:04:05.678000+00:00"

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(JiraAdapter, "get")
    def test_get_comments_returns_dto_list(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """get_comments() returns JiraCommentDTO list."""
        mock_get.return_value = MagicMock()
        mock_jira = mock_jira_cls.return_value
        mock_comment = MagicMock()
        mock_comment.id = "C-4"
        mock_comment.body = "First comment"
        author_mock = MagicMock()
        author_mock.key = "reporter"
        mock_comment.author = author_mock
        mock_comment.created = "2023-02-02T03:04:05.678Z"
        mock_comment.visibility = None
        mock_jira.comments.return_value = [mock_comment]

        adapter = JiraAdapter(jira_settings)
        result = adapter.get_comments("PROJ-4")

        mock_jira.comments.assert_called_once_with("PROJ-4")
        assert isinstance(result, list)
        assert result and result[0].id == "C-4"
        assert result[0].author == "reporter"
        assert result[0].body == "First comment"
        assert result[0].is_internal is False

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(JiraAdapter, "get")
    def test_get_comments_returns_empty_for_no_comments(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """get_comments() returns empty list when no comments exist."""
        mock_get.return_value = MagicMock()
        mock_jira = mock_jira_cls.return_value
        mock_jira.comments.return_value = []

        adapter = JiraAdapter(jira_settings)
        result = adapter.get_comments("PROJ-5")

        assert result == []

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(
        JiraAdapter,
        "get",
        side_effect=JiraNotFoundError("PROJ-404"),
    )
    def test_get_comments_raises_not_found(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """get_comments() surfaces JiraNotFoundError when issue missing."""
        adapter = JiraAdapter(jira_settings)

        with pytest.raises(JiraNotFoundError):
            adapter.get_comments("PROJ-404")

        mock_jira_cls.return_value.comments.assert_not_called()
        mock_get.assert_called_once_with("PROJ-404")

    @patch("buvis.pybase.adapters.jira.jira.JIRA")
    @patch.object(JiraAdapter, "get")
    def test_get_comments_preserves_order(
        self,
        mock_get: MagicMock,
        mock_jira_cls: MagicMock,
        jira_settings: JiraSettings,
    ) -> None:
        """Comments are returned in the order JIRA provides."""
        mock_get.return_value = MagicMock()
        mock_jira = mock_jira_cls.return_value
        first_comment = MagicMock()
        first_comment.id = "C-1"
        first_comment.body = "First"
        author_first = MagicMock()
        author_first.key = "first-user"
        first_comment.author = author_first
        first_comment.created = "2023-02-02T03:00:00.000Z"
        first_comment.visibility = None
        second_comment = MagicMock()
        second_comment.id = "C-2"
        second_comment.body = "Second"
        author_second = MagicMock()
        author_second.key = "second-user"
        second_comment.author = author_second
        second_comment.created = "2023-02-02T03:01:00.000Z"
        second_comment.visibility = MagicMock()
        mock_jira.comments.return_value = [first_comment, second_comment]

        adapter = JiraAdapter(jira_settings)
        result = adapter.get_comments("PROJ-6")

        assert [c.id for c in result] == ["C-1", "C-2"]
        assert result[0].is_internal is False
        assert result[1].is_internal is True
