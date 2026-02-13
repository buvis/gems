from pathlib import Path

import pytest
from buvis.pybase.zettel.domain.value_objects.property_schema import BUILTIN_SCHEMA, PropertyDef
from buvis.pybase.zettel.infrastructure.query.query_spec_parser import (
    list_query_files,
    parse_query_spec,
    parse_query_string,
    resolve_query_file,
)


class TestParseQuerySpec:
    def test_minimal_spec(self):
        spec = parse_query_spec({})
        assert spec.source.directory is None
        assert spec.filter is None
        assert spec.sort == []
        assert spec.columns == []

    def test_source_parsing(self):
        spec = parse_query_spec(
            {
                "source": {"directory": "~/notes", "recursive": False, "extensions": ["md", "txt"]},
            }
        )
        assert spec.source.directory == "~/notes"
        assert spec.source.recursive is False
        assert spec.source.extensions == ["md", "txt"]

    def test_simple_filter(self):
        spec = parse_query_spec({"filter": {"type": {"eq": "project"}}})
        assert spec.filter is not None
        assert spec.filter.field == "type"
        assert spec.filter.operator == "eq"
        assert spec.filter.value == "project"

    def test_and_filter(self):
        spec = parse_query_spec(
            {
                "filter": {
                    "and": [
                        {"type": {"eq": "project"}},
                        {"tags": {"contains": "sprint-1"}},
                    ],
                },
            }
        )
        assert spec.filter.combinator == "and"
        assert len(spec.filter.children) == 2
        assert spec.filter.children[0].field == "type"
        assert spec.filter.children[1].field == "tags"

    def test_or_filter(self):
        spec = parse_query_spec(
            {
                "filter": {
                    "or": [
                        {"type": {"eq": "note"}},
                        {"type": {"eq": "project"}},
                    ],
                },
            }
        )
        assert spec.filter.combinator == "or"
        assert len(spec.filter.children) == 2

    def test_not_filter(self):
        spec = parse_query_spec(
            {
                "filter": {"not": {"processed": {"eq": True}}},
            }
        )
        assert spec.filter.combinator == "not"
        assert len(spec.filter.children) == 1
        assert spec.filter.children[0].field == "processed"

    def test_nested_filter(self):
        spec = parse_query_spec(
            {
                "filter": {
                    "and": [
                        {"type": {"eq": "project"}},
                        {"not": {"processed": {"eq": True}}},
                        {
                            "or": [
                                {"tags": {"contains": "a"}},
                                {"tags": {"contains": "b"}},
                            ]
                        },
                    ],
                },
            }
        )
        assert spec.filter.combinator == "and"
        assert len(spec.filter.children) == 3
        assert spec.filter.children[1].combinator == "not"
        assert spec.filter.children[2].combinator == "or"

    def test_sort_parsing(self):
        spec = parse_query_spec(
            {
                "sort": [
                    {"field": "date", "order": "desc"},
                    {"field": "title"},
                ],
            }
        )
        assert len(spec.sort) == 2
        assert spec.sort[0].field == "date"
        assert spec.sort[0].order == "desc"
        assert spec.sort[1].field == "title"
        assert spec.sort[1].order == "asc"

    def test_columns_parsing(self):
        spec = parse_query_spec(
            {
                "columns": [
                    {"field": "id"},
                    {"field": "date", "format": "%Y-%m-%d"},
                    {"expr": "len(tags)", "label": "Tag Count"},
                ],
            }
        )
        assert len(spec.columns) == 3
        assert spec.columns[0].field == "id"
        assert spec.columns[1].format == "%Y-%m-%d"
        assert spec.columns[2].expr == "len(tags)"
        assert spec.columns[2].label == "Tag Count"

    def test_output_parsing(self):
        spec = parse_query_spec(
            {
                "output": {"format": "csv", "file": "out.csv", "limit": 50},
            }
        )
        assert spec.output.format == "csv"
        assert spec.output.file == "out.csv"
        assert spec.output.limit == 50

    def test_invalid_operator(self):
        with pytest.raises(ValueError, match="Unknown operator"):
            parse_query_spec({"filter": {"type": {"bogus": "x"}}})

    def test_column_needs_field_or_expr(self):
        with pytest.raises(ValueError, match="field.*expr"):
            parse_query_spec({"columns": [{"label": "oops"}]})

    def test_expr_filter(self):
        spec = parse_query_spec({"filter": {"expr": "len(tags) > 1"}})
        assert spec.filter.expr == "len(tags) > 1"
        assert spec.filter.field is None
        assert spec.filter.operator is None

    def test_expr_filter_in_and(self):
        spec = parse_query_spec(
            {
                "filter": {
                    "and": [
                        {"type": {"eq": "project"}},
                        {"expr": "len(tags) > 1"},
                    ],
                },
            }
        )
        assert spec.filter.combinator == "and"
        assert spec.filter.children[1].expr == "len(tags) > 1"

    def test_column_widget_fields(self):
        spec = parse_query_spec(
            {
                "columns": [
                    {"field": "title", "widget": "link"},
                    {
                        "field": "priority",
                        "widget": "select",
                        "editable": True,
                        "options": ["low", "high"],
                    },
                    {"field": "done", "widget": "checkbox", "editable": True},
                ],
            }
        )
        assert spec.columns[0].widget == "link"
        assert spec.columns[0].editable is False
        assert spec.columns[1].widget == "select"
        assert spec.columns[1].editable is True
        assert spec.columns[1].options == ["low", "high"]
        assert spec.columns[2].widget == "checkbox"

    def test_editable_auto_injects_file_path(self):
        spec = parse_query_spec(
            {
                "columns": [
                    {"field": "title"},
                    {"field": "done", "editable": True},
                ],
            }
        )
        fields = [c.field for c in spec.columns]
        assert "file_path" in fields

    def test_editable_no_duplicate_file_path(self):
        spec = parse_query_spec(
            {
                "columns": [
                    {"field": "title"},
                    {"field": "done", "editable": True},
                    {"field": "file_path"},
                ],
            }
        )
        fp_count = sum(1 for c in spec.columns if c.field == "file_path")
        assert fp_count == 1

    def test_dashboard_parsing(self):
        spec = parse_query_spec(
            {
                "dashboard": {"title": "My Board", "auto_refresh": False},
            }
        )
        assert spec.dashboard is not None
        assert spec.dashboard.title == "My Board"
        assert spec.dashboard.auto_refresh is False

    def test_no_dashboard_defaults_none(self):
        spec = parse_query_spec({})
        assert spec.dashboard is None


class TestSchemaParser:
    def test_schema_parsing(self):
        spec = parse_query_spec(
            {
                "schema": {
                    "deliverable": {
                        "type": "select",
                        "label": "Deliverable",
                        "options": ["enhancement", "bugfix"],
                    },
                    "priority": {
                        "type": "number",
                        "label": "Priority",
                    },
                },
            }
        )
        assert "deliverable" in spec.schema
        assert spec.schema["deliverable"].type == "select"
        assert spec.schema["deliverable"].label == "Deliverable"
        assert spec.schema["deliverable"].options == ["enhancement", "bugfix"]
        assert spec.schema["priority"].type == "number"
        assert spec.schema["priority"].options == []

    def test_schema_empty_defaults(self):
        spec = parse_query_spec({})
        assert spec.schema == {}

    def test_schema_type_defaults_to_text(self):
        spec = parse_query_spec(
            {
                "schema": {
                    "custom": {"label": "Custom Field"},
                },
            }
        )
        assert spec.schema["custom"].type == "text"

    def test_builtin_schema_has_expected_fields(self):
        assert "id" in BUILTIN_SCHEMA
        assert "title" in BUILTIN_SCHEMA
        assert "tags" in BUILTIN_SCHEMA
        assert "completed" in BUILTIN_SCHEMA
        assert "file_path" in BUILTIN_SCHEMA
        assert BUILTIN_SCHEMA["completed"].type == "bool"
        assert BUILTIN_SCHEMA["tags"].type == "tags"
        assert BUILTIN_SCHEMA["type"].type == "select"
        assert isinstance(BUILTIN_SCHEMA["type"].options, list)


class TestItemParser:
    def test_item_parsing(self):
        spec = parse_query_spec(
            {
                "item": {
                    "title": "{title}",
                    "subtitle": "{type} | {date}",
                    "sections": [
                        {
                            "heading": "Properties",
                            "fields": [
                                {"field": "tags"},
                                {"field": "completed", "editable": True},
                            ],
                        },
                        {
                            "heading": "Description",
                            "section": "## Description",
                            "editable": True,
                        },
                    ],
                },
            }
        )
        assert spec.item is not None
        assert spec.item.title == "{title}"
        assert spec.item.subtitle == "{type} | {date}"
        assert len(spec.item.sections) == 2

        props = spec.item.sections[0]
        assert props.heading == "Properties"
        assert props.fields is not None
        assert len(props.fields) == 2
        assert props.fields[0].field == "tags"
        assert props.fields[0].editable is False
        assert props.fields[1].field == "completed"
        assert props.fields[1].editable is True

        desc = spec.item.sections[1]
        assert desc.heading == "Description"
        assert desc.section == "## Description"
        assert desc.editable is True
        assert desc.fields is None

    def test_no_item_defaults_none(self):
        spec = parse_query_spec({})
        assert spec.item is None

    def test_item_defaults(self):
        spec = parse_query_spec({"item": {}})
        assert spec.item is not None
        assert spec.item.title == "{title}"
        assert spec.item.subtitle is None
        assert spec.item.sections == []


class TestActionsParser:
    def test_actions_parsing(self):
        spec = parse_query_spec(
            {
                "actions": [
                    {
                        "name": "sync_jira",
                        "label": "Sync to Jira",
                        "scope": "item",
                        "handler": "sync_note",
                        "confirm": "Create Jira issue?",
                        "args": {"target_system": "jira"},
                    },
                    {
                        "name": "mark_done",
                        "label": "Mark done",
                        "scope": "list",
                        "handler": "patch",
                        "args": {"field": "completed", "value": True},
                    },
                ],
            }
        )
        assert len(spec.actions) == 2

        a0 = spec.actions[0]
        assert a0.name == "sync_jira"
        assert a0.label == "Sync to Jira"
        assert a0.scope == "item"
        assert a0.handler == "sync_note"
        assert a0.confirm == "Create Jira issue?"
        assert a0.args == {"target_system": "jira"}

        a1 = spec.actions[1]
        assert a1.name == "mark_done"
        assert a1.scope == "list"
        assert a1.confirm is None

    def test_no_actions_defaults_empty(self):
        spec = parse_query_spec({})
        assert spec.actions == []

    def test_action_defaults(self):
        spec = parse_query_spec(
            {
                "actions": [
                    {"name": "test", "label": "Test"},
                ],
            }
        )
        a = spec.actions[0]
        assert a.scope == "item"
        assert a.handler == "patch"
        assert a.args == {}
        assert a.confirm is None

    def test_action_missing_name_raises(self):
        with pytest.raises(ValueError, match="name.*label"):
            parse_query_spec({"actions": [{"label": "oops"}]})

    def test_action_missing_label_raises(self):
        with pytest.raises(ValueError, match="name.*label"):
            parse_query_spec({"actions": [{"name": "oops"}]})


class TestParseQueryString:
    def test_inline_yaml(self):
        spec = parse_query_string("{filter: {type: {eq: project}}}")
        assert spec.filter.field == "type"
        assert spec.filter.value == "project"

    def test_invalid_yaml(self):
        with pytest.raises(ValueError, match="YAML mapping"):
            parse_query_string("just a string")


class TestResolveQueryFile:
    def test_path_with_slash_returned_as_is(self) -> None:
        result = resolve_query_file("/some/path/query.yaml")
        assert result == Path("/some/path/query.yaml")

    def test_path_ending_yaml_returned_as_is(self) -> None:
        result = resolve_query_file("my_query.yaml")
        assert result == Path("my_query.yaml")

    def test_path_ending_yml_returned_as_is(self) -> None:
        result = resolve_query_file("my_query.yml")
        assert result == Path("my_query.yml")

    def test_name_resolved_from_config_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        queries_dir = tmp_path / "queries"
        queries_dir.mkdir()
        (queries_dir / "my_query.yaml").write_text("filter: {}")

        result = resolve_query_file("my_query")

        assert result == queries_dir / "my_query.yaml"

    def test_bundled_dir_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path / "empty"))
        bundled = tmp_path / "bundled"
        bundled.mkdir()
        (bundled / "builtin.yaml").write_text("filter: {}")

        result = resolve_query_file("builtin", bundled_dir=bundled)

        assert result == bundled / "builtin.yaml"

    def test_user_overrides_bundled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        queries_dir = tmp_path / "queries"
        queries_dir.mkdir()
        user_file = queries_dir / "shared.yaml"
        user_file.write_text("filter: {type: {eq: note}}")

        bundled = tmp_path / "bundled"
        bundled.mkdir()
        (bundled / "shared.yaml").write_text("filter: {type: {eq: project}}")

        result = resolve_query_file("shared", bundled_dir=bundled)

        assert result == user_file

    def test_not_found_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))

        with pytest.raises(FileNotFoundError, match="nonexistent"):
            resolve_query_file("nonexistent")


class TestListQueryFiles:
    def test_discovers_bundled(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        bundled.mkdir()
        (bundled / "q1.yaml").write_text("filter: {}")
        (bundled / "q2.yaml").write_text("filter: {}")

        result = list_query_files(bundled_dir=bundled)

        assert set(result.keys()) == {"q1", "q2"}

    def test_config_overrides_bundled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        queries_dir = tmp_path / "queries"
        queries_dir.mkdir()
        user_file = queries_dir / "shared.yaml"
        user_file.write_text("filter: {}")

        bundled = tmp_path / "bundled"
        bundled.mkdir()
        (bundled / "shared.yaml").write_text("filter: {}")
        (bundled / "only_bundled.yaml").write_text("filter: {}")

        result = list_query_files(bundled_dir=bundled)

        assert result["shared"] == user_file
        assert result["only_bundled"] == bundled / "only_bundled.yaml"

    def test_empty_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))

        result = list_query_files()

        assert result == {}
