from __future__ import annotations

import re

import pytest
from buvis.pybase.zettel.domain.templates.meeting_minutes import MeetingMinutesTemplate

TITLE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2} \| .+ meeting minutes$")


class TestMeetingMinutesTemplate:
    def test_name_and_body_section(self) -> None:
        t = MeetingMinutesTemplate()
        assert t.name == "meeting-minutes"
        assert t.body_section == "## Log"
        assert t.hooks() == []

    def test_questions_require_a_vault_location(self) -> None:
        qs = MeetingMinutesTemplate().questions()
        assert [q.key for q in qs] == ["location", "organizer"]
        assert qs[0].choices == ["webex", "teams", "phone", "face to face"]
        assert qs[0].required is True
        assert qs[0].default is None
        assert qs[1].default == ""

    @pytest.mark.parametrize("title", ["weekly sync", "weekly sync meeting minutes", "Weekly sync Meeting Minutes "])
    def test_title_is_todays_date_and_capitalised_subject(self, title: str) -> None:
        data = MeetingMinutesTemplate().build_data({"title": title, "location": "teams"})

        assert TITLE_SHAPE.fullmatch(data.metadata["title"])
        assert data.metadata["title"] == f"{data.metadata['date']:%Y-%m-%d} | Weekly sync meeting minutes"
        assert data.sections[0] == (f"# {data.metadata['title']}", "")

    def test_metadata_and_sections_match_the_vault_template(self) -> None:
        data = MeetingMinutesTemplate().build_data(
            {"title": "Retro", "location": "phone", "organizer": "Ada", "tags": "x"}
        )

        assert data.metadata["type"] == "meeting-minutes"
        assert data.metadata["location"] == "phone"
        assert data.metadata["start"] == "hh:mm"
        assert data.metadata["end"] == "hh:mm"
        assert data.metadata["organizer"] == "Ada"
        assert data.metadata["attendees"] == [""]
        assert data.metadata["summary"] == ""
        assert data.metadata["tags"] == ["x"]
        assert data.metadata["date"].microsecond == 0
        assert [heading for heading, _ in data.sections] == [
            f"# {data.metadata['title']}",
            "## Agenda",
            "## Log",
            "## Post-processing",
        ]
        assert data.sections[2][1] == ""
        assert data.sections[3][1] == (
            "Don't forget to write a summary into frontmatter!\n\n"
            "Go through the log and record actions into GTD lists below.\n\n"
            "#gtd/act/now\n\n#gtd/act/next\n\n#gtd/wait\n\n#gtd/act/someday"
        )

    @pytest.mark.parametrize("title", ["meeting minutes", "  Meeting Minutes", ""])
    def test_empty_subject_is_rejected(self, title: str) -> None:
        with pytest.raises(ValueError, match="meeting title needs a subject, not just 'meeting minutes'"):
            MeetingMinutesTemplate().build_data({"title": title, "location": "teams"})
