from __future__ import annotations

from bim.dependencies import (
    get_evaluator,
    get_formatter,
    get_hook_runner,
    get_repo,
    get_templates,
    parse_query_string,
)


class TestBimDependencies:
    def test_get_repo(self) -> None:
        repo = get_repo()
        assert repo is not None

    def test_get_repo_with_extensions(self) -> None:
        repo = get_repo(extensions=[".md"])
        assert repo is not None

    def test_get_formatter(self) -> None:
        formatter = get_formatter()
        assert formatter is not None

    def test_get_evaluator(self) -> None:
        evaluator = get_evaluator()
        assert evaluator is not None

    def test_get_templates(self) -> None:
        templates = get_templates()
        assert isinstance(templates, dict)

    def test_get_hook_runner(self) -> None:
        runner = get_hook_runner()
        assert callable(runner)

    def test_parse_query_string(self) -> None:
        yaml_str = "source:\n  directory: /tmp\nfilter:\n  type: {eq: note}\ncolumns:\n  - field: title\n"
        spec = parse_query_string(yaml_str)
        assert spec is not None
