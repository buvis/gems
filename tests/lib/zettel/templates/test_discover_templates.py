from __future__ import annotations

from buvis.pybase.zettel.domain.templates import Hook, Question, _discover_python_templates


class TestDiscoverTemplates:
    def test_discovers_project_template(self) -> None:
        templates = _discover_python_templates()
        assert "project" in templates
        assert templates["project"].name == "project"

    def test_template_has_questions(self) -> None:
        templates = _discover_python_templates()
        for name, tmpl in templates.items():
            questions = tmpl.questions()
            assert isinstance(questions, list)

    def test_template_has_hooks(self) -> None:
        templates = _discover_python_templates()
        for name, tmpl in templates.items():
            hooks = tmpl.hooks()
            assert isinstance(hooks, list)


class TestQuestion:
    def test_question_defaults(self) -> None:
        q = Question(key="title", prompt="Enter title")
        assert q.default is None
        assert q.choices is None
        assert q.required is False

    def test_question_with_choices(self) -> None:
        q = Question(key="type", prompt="Pick type", choices=["note", "project"], required=True)
        assert q.choices == ["note", "project"]
        assert q.required is True


class TestHook:
    def test_hook_name(self) -> None:
        h = Hook(name="post_create")
        assert h.name == "post_create"
