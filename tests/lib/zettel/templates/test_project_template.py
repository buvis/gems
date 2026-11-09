from __future__ import annotations

from datetime import datetime

from buvis.pybase.zettel.domain.templates.project import ProjectTemplate


class TestProjectTemplate:
    def test_name_and_body_section(self) -> None:
        t = ProjectTemplate()
        assert t.name == "project"
        assert t.body_section == "## Solution"

    def test_questions_ask_for_deliverable_and_optional_ticket(self) -> None:
        qs = ProjectTemplate().questions()
        assert [q.key for q in qs] == ["deliverable", "ticket"]
        assert qs[0].choices == ["fix", "enhancement", "support"]
        assert qs[0].required is True
        assert qs[0].default is None
        assert qs[1].required is False

    def test_build_data_reproduces_vault_project_shape(self) -> None:
        data = ProjectTemplate().build_data({"title": "Probe", "deliverable": "fix", "ticket": "SR-1", "tags": "a, b"})

        now = data.metadata["date"]
        assert isinstance(now, datetime)
        assert now.tzinfo is not None
        assert now.microsecond == 0
        assert data.metadata["type"] == "project"
        assert data.metadata["title"] == "Probe"
        assert data.metadata["completed"] is False
        assert data.metadata["deliverable"] == "fix"
        assert data.metadata["tags"] == ["a", "b"]
        assert "dev-type" not in data.metadata
        assert [heading for heading, _ in data.sections] == [
            "# Probe",
            "## Description",
            "## Log",
            "## Plan",
            "## Solution",
        ]
        assert data.sections[1][1] == "One paragraph summarizing the problem statement."
        assert data.sections[2][1] == (
            f"- [ ] {now:%Y-%m-%d %H:%M} - plan the next action to move this project forward"
            f" | #gtd/act/now 📅 {now:%Y-%m-%d}"
        )
        assert data.sections[3][1] == "Plan the steps to complete the project. Use templates for recurring projects."
        assert data.sections[4][1] == "Describe what was done to get project closure acceptance."
        assert data.reference == {"parent": "", "ticket": "SR-1", "us": "", "psd": ""}
        assert list(data.reference) == ["parent", "ticket", "us", "psd"]

    def test_blank_ticket_is_left_out_of_backmatter(self) -> None:
        data = ProjectTemplate().build_data({"title": "Probe", "deliverable": "support", "ticket": "  "})
        assert list(data.reference) == ["parent", "us", "psd"]

    def test_hooks_set_parent_then_create_resources_folder(self) -> None:
        assert [hook.name for hook in ProjectTemplate().hooks()] == ["set_parent_reference", "create_project_dir"]
