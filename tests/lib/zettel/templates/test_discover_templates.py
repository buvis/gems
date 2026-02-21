from __future__ import annotations

from buvis.pybase.zettel.domain.templates import _discover_python_templates


class TestDiscoverTemplates:
    def test_discovers_project_template(self) -> None:
        templates = _discover_python_templates()
        assert "project" in templates
        assert templates["project"].name == "project"
