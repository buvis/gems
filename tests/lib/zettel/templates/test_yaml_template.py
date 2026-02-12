from __future__ import annotations

from buvis.pybase.zettel.domain.templates.yaml_template import YamlTemplate


class TestYamlTemplateBasic:
    def test_name(self):
        t = YamlTemplate({"name": "test"})
        assert t.name == "test"

    def test_questions(self):
        t = YamlTemplate({
            "name": "test",
            "questions": [
                {"key": "who", "prompt": "Who?", "required": True},
                {"key": "where", "prompt": "Where?", "default": "online"},
            ],
        })
        qs = t.questions()
        assert len(qs) == 2
        assert qs[0].key == "who"
        assert qs[0].required is True
        assert qs[1].default == "online"

    def test_questions_with_choices(self):
        t = YamlTemplate({
            "name": "test",
            "questions": [
                {"key": "loc", "prompt": "Location", "choices": ["a", "b"]},
            ],
        })
        assert t.questions()[0].choices == ["a", "b"]

    def test_no_questions(self):
        t = YamlTemplate({"name": "test"})
        assert t.questions() == []

    def test_hooks_empty(self):
        t = YamlTemplate({"name": "test"})
        assert t.hooks() == []


class TestYamlTemplateBuildData:
    def test_metadata_string_substitution(self):
        t = YamlTemplate({
            "name": "test",
            "metadata": {"type": "meeting", "attendees": "{attendees}"},
        })
        data = t.build_data({"title": "Standup", "attendees": "Alice, Bob"})
        assert data.metadata["type"] == "meeting"
        assert data.metadata["attendees"] == "Alice, Bob"

    def test_metadata_missing_key_empty_string(self):
        t = YamlTemplate({
            "name": "test",
            "metadata": {"note": "{missing_key}"},
        })
        data = t.build_data({"title": "X"})
        assert data.metadata["note"] == ""

    def test_metadata_eval(self):
        t = YamlTemplate({
            "name": "test",
            "metadata": {"tag_count": {"eval": "len(tags) if tags else 0"}},
        })
        data = t.build_data({"title": "X", "tags": ["a", "b", "c"]})
        assert data.metadata["tag_count"] == 3

    def test_metadata_eval_no_tags(self):
        t = YamlTemplate({
            "name": "test",
            "metadata": {"tag_count": {"eval": "len(tags) if tags else 0"}},
        })
        data = t.build_data({"title": "X", "tags": []})
        assert data.metadata["tag_count"] == 0

    def test_metadata_passthrough(self):
        t = YamlTemplate({
            "name": "test",
            "metadata": {"count": 42, "flag": True},
        })
        data = t.build_data({"title": "X"})
        assert data.metadata["count"] == 42
        assert data.metadata["flag"] is True

    def test_sections(self):
        t = YamlTemplate({
            "name": "test",
            "sections": [
                {"heading": "# {title}", "body": ""},
                {"heading": "## Notes", "body": "some body"},
            ],
        })
        data = t.build_data({"title": "My Note"})
        assert data.sections == [("# My Note", ""), ("## Notes", "some body")]

    def test_sections_missing_body(self):
        t = YamlTemplate({
            "name": "test",
            "sections": [{"heading": "# H1"}],
        })
        data = t.build_data({"title": "X"})
        assert data.sections == [("# H1", "")]

    def test_no_sections_keeps_default(self):
        t = YamlTemplate({"name": "test"})
        data = t.build_data({"title": "X"})
        assert data.sections == []

    def test_title_set_without_base(self):
        t = YamlTemplate({"name": "test"})
        data = t.build_data({"title": "My Title"})
        assert data.metadata["title"] == "My Title"


class TestYamlTemplateExtends:
    def _make_base(self):
        """Create a note-like base template."""
        return YamlTemplate({
            "name": "note",
            "questions": [{"key": "context", "prompt": "Context?"}],
            "metadata": {"type": "note"},
            "sections": [{"heading": "# {title}", "body": ""}],
        })

    def test_extends_merges_questions(self):
        base = self._make_base()
        child = YamlTemplate(
            {"name": "standup", "extends": "note",
             "questions": [{"key": "sprint", "prompt": "Sprint?"}]},
            base=base,
        )
        qs = child.questions()
        assert len(qs) == 2
        assert qs[0].key == "context"
        assert qs[1].key == "sprint"

    def test_extends_metadata_overrides(self):
        base = self._make_base()
        child = YamlTemplate(
            {"name": "standup", "extends": "note",
             "metadata": {"type": "standup", "sprint": "{sprint}"}},
            base=base,
        )
        data = child.build_data({"title": "Daily", "sprint": "S1"})
        assert data.metadata["type"] == "standup"
        assert data.metadata["sprint"] == "S1"

    def test_extends_sections_override(self):
        base = self._make_base()
        child = YamlTemplate(
            {"name": "standup", "extends": "note",
             "sections": [{"heading": "# Standup"}]},
            base=base,
        )
        data = child.build_data({"title": "Daily"})
        assert len(data.sections) == 1
        assert data.sections[0][0] == "# Standup"

    def test_extends_sections_inherited(self):
        base = self._make_base()
        child = YamlTemplate(
            {"name": "standup", "extends": "note",
             "metadata": {"sprint": "1"}},
            base=base,
        )
        data = child.build_data({"title": "Daily"})
        assert data.sections == [("# Daily", "")]

    def test_extends_hooks_from_base(self):
        from buvis.pybase.zettel.domain.templates.project import ProjectTemplate
        base = ProjectTemplate()
        child = YamlTemplate(
            {"name": "custom-project", "extends": "project"},
            base=base,
        )
        assert len(child.hooks()) == 1
        assert child.hooks()[0].name == "create_project_dir"
