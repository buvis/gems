from __future__ import annotations

from buvis.pybase.zettel.domain.templates.project import ProjectTemplate


class TestProjectTemplate:
    def test_name(self) -> None:
        t = ProjectTemplate()
        assert t.name == "project"

    def test_questions(self) -> None:
        t = ProjectTemplate()
        qs = t.questions()
        assert len(qs) == 1
        assert qs[0].key == "dev_type"
        assert "feature" in qs[0].choices

    def test_build_data(self) -> None:
        t = ProjectTemplate()
        data = t.build_data({"title": "Test", "dev_type": "bugfix", "tags": "a, b"})
        assert data.metadata["type"] == "project"
        assert data.metadata["title"] == "Test"
        assert data.metadata["dev-type"] == "bugfix"
        assert data.metadata["tags"] == ["a", "b"]
        assert any("# Test" in s[0] for s in data.sections)

    def test_build_data_defaults(self) -> None:
        t = ProjectTemplate()
        data = t.build_data({})
        assert data.metadata["dev-type"] == "feature"
        assert data.metadata["completed"] is False

    def test_hooks(self) -> None:
        t = ProjectTemplate()
        hooks = t.hooks()
        assert len(hooks) == 1
        assert hooks[0].name == "create_project_dir"
