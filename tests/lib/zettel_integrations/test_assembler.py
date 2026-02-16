import pytest
from buvis.pybase.zettel.integrations.jira.assemblers.project_zettel_jira_issue import (
    ProjectZettelJiraIssueDTOAssembler,
    _get_ticket_references,
)


def _make_defaults(**overrides):
    base = {
        "project": "PROJ",
        "region": "EU",
        "user": "alice",
        "team": "alpha",
        "enhancements": {
            "issue_type": "Story",
            "feature": "feat-1",
            "labels": "enh,frontend",
            "priority": "Medium",
        },
        "bugs": {
            "issue_type": "Bug",
            "feature": "feat-bug",
            "labels": "bug,backend",
            "priority": "High",
        },
    }
    base.update(overrides)
    return base


@pytest.fixture
def zettel_factory(make_zettel):
    def _factory(
        *,
        title: str = "Test task",
        deliverable: str = "enhancement",
        tags: list[str] | None = None,
        ticket: str | None = None,
        ticket_related: str | None = None,
        sections: list[tuple[str, str]] | None = None,
    ):
        extra_meta = {"deliverable": deliverable}
        if ticket is not None:
            extra_meta["ticket"] = ticket
        if ticket_related is not None:
            extra_meta["ticket_related"] = ticket_related
        return make_zettel(
            title=title,
            tags=tags or [],
            extra_meta=extra_meta,
            sections=sections or [],
        )

    return _factory


class TestToDtoValidation:
    def test_missing_project_raises(self, zettel_factory):
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults={"region": "EU", "user": "u", "team": "t"})
        with pytest.raises(ValueError, match="project"):
            assembler.to_dto(zettel_factory())

    def test_missing_region_raises(self, zettel_factory):
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults={"project": "P", "user": "u", "team": "t"})
        with pytest.raises(ValueError, match="region"):
            assembler.to_dto(zettel_factory())

    def test_missing_user_raises(self, zettel_factory):
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults={"project": "P", "region": "EU", "team": "t"})
        with pytest.raises(ValueError, match="user"):
            assembler.to_dto(zettel_factory())

    def test_missing_team_raises(self, zettel_factory):
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults={"project": "P", "region": "EU", "user": "u"})
        with pytest.raises(ValueError, match="team"):
            assembler.to_dto(zettel_factory())


class TestToDtoMapping:
    def test_enhancement_mapping(self, zettel_factory):
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults=_make_defaults())
        dto = assembler.to_dto(zettel_factory(deliverable="enhancement"))

        assert dto.issue_type == "Story"
        assert dto.feature == "feat-1"
        assert dto.labels == ["enh", "frontend"]
        assert dto.priority == "Medium"

    def test_bug_mapping(self, zettel_factory):
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults=_make_defaults())
        dto = assembler.to_dto(zettel_factory(deliverable="bug"))

        assert dto.issue_type == "Bug"
        assert dto.feature == "feat-bug"
        assert dto.labels == ["bug", "backend"]
        assert dto.priority == "High"

    def test_pex_tag_prefixes_title(self, zettel_factory):
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults=_make_defaults())
        dto = assembler.to_dto(zettel_factory(title="Fix login", tags=["pex"]))

        assert dto.title == "PEX: Fix login"

    def test_no_pex_tag_keeps_title(self, zettel_factory):
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults=_make_defaults())
        dto = assembler.to_dto(zettel_factory(title="Fix login", tags=["other"]))

        assert dto.title == "Fix login"

    def test_description_from_section(self, zettel_factory):
        sections = [("## Description", "  Detailed explanation  ")]
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults=_make_defaults())
        dto = assembler.to_dto(zettel_factory(sections=sections))

        assert dto.description == "Detailed explanation"

    def test_default_description_when_no_section(self, zettel_factory):
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults=_make_defaults())
        dto = assembler.to_dto(zettel_factory(sections=[]))

        assert dto.description == "No description provided"

    def test_common_fields(self, zettel_factory):
        assembler = ProjectZettelJiraIssueDTOAssembler(defaults=_make_defaults())
        zettel = zettel_factory(ticket="SR-123")
        dto = assembler.to_dto(zettel)

        assert dto.project == "PROJ"
        assert dto.assignee == "alice"
        assert dto.reporter == "alice"
        assert dto.team == "alpha"
        assert dto.region == "EU"
        assert dto.ticket == "SR-123"


class TestGetTicketReferences:
    def test_no_ticket_no_related(self, zettel_factory):
        zettel = zettel_factory(ticket=None, ticket_related=None)
        assert _get_ticket_references(zettel) == ""

    def test_single_ticket(self, zettel_factory):
        zettel = zettel_factory(ticket="SR-100")
        assert _get_ticket_references(zettel) == "This solves SR SR-100."

    def test_single_related(self, zettel_factory):
        zettel = zettel_factory(ticket=None, ticket_related="SR-200")
        assert _get_ticket_references(zettel) == " Related SR: SR-200."

    def test_ticket_and_single_related(self, zettel_factory):
        zettel = zettel_factory(ticket="SR-100", ticket_related="SR-200")
        result = _get_ticket_references(zettel)
        assert "This solves SR SR-100." in result
        assert "Related SR: SR-200." in result

    def test_two_related_tickets(self, zettel_factory):
        zettel = zettel_factory(ticket=None, ticket_related="SR-300 SR-200")
        result = _get_ticket_references(zettel)
        assert "SR-200 and SR-300" in result

    def test_multiple_related_tickets(self, zettel_factory):
        zettel = zettel_factory(ticket=None, ticket_related="SR-300 SR-100 SR-200")
        result = _get_ticket_references(zettel)
        assert "SR-100, SR-200, and SR-300" in result
