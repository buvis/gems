"""Tests for ConfigWriter."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Union

import pytest
import yaml
from pydantic import BaseModel

from buvis.pybase.configuration import ConfigWriter


class NestedModel(BaseModel):
    """Sample nested model for testing."""

    value: str


class TestFormatType:
    """Tests for ConfigWriter._format_type."""

    @pytest.mark.parametrize(
        ("type_", "expected"),
        [
            (Literal["a", "b"], "one of: 'a', 'b'"),
            (Literal["DEBUG"], "one of: 'DEBUG'"),
        ],
    )
    def test_literal(self, type_, expected: str) -> None:
        assert ConfigWriter._format_type(type_) == expected

    @pytest.mark.parametrize(
        ("type_", "expected"),
        [
            (str | None, "str | None (optional)"),
            (Path | None, "Path | None (optional)"),
            (Union[str, None], "str | None (optional)"),
        ],
    )
    def test_optional(self, type_, expected: str) -> None:
        assert ConfigWriter._format_type(type_) == expected

    @pytest.mark.parametrize(
        ("type_", "expected"),
        [
            (int | str, "int | str"),
            (str | int | None, "str | int | None"),
        ],
    )
    def test_union(self, type_, expected: str) -> None:
        assert ConfigWriter._format_type(type_) == expected

    @pytest.mark.parametrize(
        ("type_", "expected"),
        [
            (list[str], "list[str]"),
            (dict[str, int], "dict[str, int]"),
            (list[Path], "list[Path]"),
            (list[dict[str, int]], "list[dict[str, int]]"),
        ],
    )
    def test_generic(self, type_, expected: str) -> None:
        assert ConfigWriter._format_type(type_) == expected

    @pytest.mark.parametrize(
        ("type_", "expected"),
        [
            (str, "str"),
            (int, "int"),
            (bool, "bool"),
            (Path, "Path"),
            (type(None), "None"),
        ],
    )
    def test_simple(self, type_, expected: str) -> None:
        assert ConfigWriter._format_type(type_) == expected

    def test_basemodel_subclass(self) -> None:
        assert ConfigWriter._format_type(NestedModel) == "NestedModel"


class TestFormatValue:
    """Tests for ConfigWriter._format_value."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, "null"),
            (True, "true"),
            (False, "false"),
            (42, "42"),
            (3.14, "3.14"),
            (Path("/tmp/test"), "/tmp/test"),
        ],
    )
    def test_scalar(self, value, expected: str) -> None:
        assert ConfigWriter._format_value(value) == expected

    def test_simple_string(self) -> None:
        assert ConfigWriter._format_value("simple") == "simple"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("", '""'),
            ("foo:bar", '"foo:bar"'),
            ("has#hash", '"has#hash"'),
        ],
    )
    def test_string_needing_quotes(self, value: str, expected: str) -> None:
        assert ConfigWriter._format_value(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            'foo"bar',
            "foo\\bar",
            'foo\\"bar',
            "line1\nline2",
            "line1\rline2",
            "col1\tcol2",
            "line1\nline2\ttab\rreturn",
        ],
    )
    def test_string_with_escapes_roundtrips(self, value: str) -> None:
        formatted = ConfigWriter._format_value(value)
        assert formatted.startswith('"')
        assert yaml.safe_load(formatted) == value

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ([], "[]"),
            (["a", "b"], "[a, b]"),
            ([1, None], "[1, null]"),
        ],
    )
    def test_list(self, value, expected: str) -> None:
        assert ConfigWriter._format_value(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ({}, "{}"),
            ({"a": 1}, "{a: 1}"),
            ({"x": True}, "{x: true}"),
        ],
    )
    def test_dict(self, value, expected: str) -> None:
        assert ConfigWriter._format_value(value) == expected


class SampleSettings(BaseModel):
    """Sample settings for testing field analysis."""

    required_field: str
    optional_field: str | None = None
    optional_with_default: str = "default"
    nested: NestedModel | None = None
    nested_required: NestedModel
    list_field: list[str] = []


class TestIsOptional:
    @pytest.mark.parametrize(
        ("field_name", "expected"),
        [
            ("optional_field", True),
            ("optional_with_default", False),
            ("required_field", False),
            ("nested", True),
        ],
    )
    def test_is_optional(self, field_name: str, expected: bool) -> None:
        field = SampleSettings.model_fields[field_name]
        assert ConfigWriter._is_optional(field) is expected


class TestIsRequired:
    @pytest.mark.parametrize(
        ("field_name", "expected"),
        [
            ("required_field", True),
            ("optional_with_default", False),
            ("optional_field", False),
            ("list_field", False),
            ("nested_required", True),
        ],
    )
    def test_is_required(self, field_name: str, expected: bool) -> None:
        field = SampleSettings.model_fields[field_name]
        assert ConfigWriter._is_required(field) is expected


class TestIsNestedModel:
    @pytest.mark.parametrize(
        ("type_", "expected"),
        [
            (NestedModel, True),
            (NestedModel | None, True),
            (str, False),
            (list[str], False),
        ],
    )
    def test_is_nested_model(self, type_, expected: bool) -> None:
        assert ConfigWriter._is_nested_model(type_) is expected


class TestExtractModelClass:
    @pytest.mark.parametrize(
        ("type_", "expected"),
        [
            (NestedModel, NestedModel),
            (NestedModel | None, NestedModel),
            (str, None),
            (list[str], None),
        ],
    )
    def test_extract_model_class(self, type_, expected) -> None:
        assert ConfigWriter._extract_model_class(type_) is expected


class DbWithPassword(BaseModel):
    host: str = "localhost"
    password: str = "secret"


class SettingsWithDefaultInstance(BaseModel):
    db: DbWithPassword = DbWithPassword()


class SimpleInstance(BaseModel):
    name: str = "test"
    count: int = 42


class NestedInstanceParent(BaseModel):
    label: str = "parent"
    child: SimpleInstance = SimpleInstance()


class InstanceWithSensitive(BaseModel):
    host: str = "localhost"
    password: str = "secret123"


class SettingsWithInstanceDefault(BaseModel):
    app_name: str = "myapp"
    database: InstanceWithSensitive = InstanceWithSensitive()


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432


class AppSettings(BaseModel):
    name: str = "myapp"
    database: DatabaseSettings = DatabaseSettings()


class DeepSettings(BaseModel):
    app: AppSettings = AppSettings()


class NestedWithSensitive(BaseModel):
    host: str = "localhost"
    password: str = "secret"


class TestFormatNestedModel:
    def test_flat_model_basic_types(self) -> None:
        result = ConfigWriter._format_nested_model(DatabaseSettings)
        assert "  host: localhost" in result
        assert "  port: 5432" in result

    def test_flat_model_preserves_order(self) -> None:
        result = ConfigWriter._format_nested_model(DatabaseSettings)
        lines = result.strip().split("\n")
        assert lines[0].strip().startswith("host")
        assert lines[1].strip().startswith("port")

    def test_nested_model_indentation(self) -> None:
        result = ConfigWriter._format_nested_model(AppSettings)
        assert "  name: myapp" in result
        assert "  database:" in result
        assert "    host: localhost" in result
        assert "    port: 5432" in result

    def test_required_field_empty_string(self) -> None:
        result = ConfigWriter._format_nested_model(SampleSettings)
        assert "  required_field: " in result

    def test_default_factory_list(self) -> None:
        result = ConfigWriter._format_nested_model(SampleSettings)
        assert "  list_field: []" in result

    def test_three_level_nesting(self) -> None:
        result = ConfigWriter._format_nested_model(DeepSettings)
        assert "  app:" in result
        assert "    name: myapp" in result
        assert "    database:" in result
        assert "      host: localhost" in result
        assert "      port: 5432" in result

    def test_custom_indent(self) -> None:
        result = ConfigWriter._format_nested_model(DatabaseSettings, indent=4)
        assert "    host: localhost" in result
        assert "    port: 5432" in result

    def test_sensitive_field_comment_for_nested(self) -> None:
        result = ConfigWriter._format_nested_model(NestedWithSensitive)
        lines = result.splitlines()
        for idx, line in enumerate(lines):
            if line.strip().startswith("password:"):
                assert lines[idx - 1].strip() == "# SENSITIVE - do not commit to version control"
                break
        else:
            pytest.fail("password field not found in nested output")


class TestFormatModelInstance:
    def test_basic_instance_formatting(self) -> None:
        instance = SimpleInstance(name="hello", count=99)
        result = ConfigWriter._format_model_instance(instance)
        assert "  name: hello" in result
        assert "  count: 99" in result

    def test_uses_instance_values_not_defaults(self) -> None:
        instance = SimpleInstance(name="custom", count=1)
        result = ConfigWriter._format_model_instance(instance)
        assert "custom" in result
        assert "1" in result
        assert "test" not in result

    def test_nested_instance_indentation(self) -> None:
        instance = NestedInstanceParent()
        result = ConfigWriter._format_model_instance(instance)
        assert "  label: parent" in result
        assert "  child:" in result
        assert "    name: test" in result
        assert "    count: 42" in result

    def test_custom_indent_level(self) -> None:
        instance = SimpleInstance()
        result = ConfigWriter._format_model_instance(instance, indent=4)
        assert "    name: test" in result
        assert "    count: 42" in result

    def test_sensitive_field_via_instance_path(self) -> None:
        instance = InstanceWithSensitive()
        result = ConfigWriter._format_model_instance(instance)
        lines = result.splitlines()
        for idx, line in enumerate(lines):
            if line.strip().startswith("password:"):
                assert lines[idx - 1].strip() == "# SENSITIVE - do not commit to version control"
                break
        else:
            pytest.fail("password field not found or SENSITIVE comment missing")

    def test_generate_with_model_instance_default(self) -> None:
        result = ConfigWriter.generate(SettingsWithInstanceDefault, "test")
        assert "app_name: myapp" in result
        assert "database:" in result
        assert "  host: localhost" in result
        assert "  password: secret123" in result
        assert "# SENSITIVE" in result


class FieldTestSettings(BaseModel):
    simple: str = "value"
    with_desc: str = "test"
    optional_field: str | None = None
    required_field: str
    api_key: str = "secret"
    password: str
    nested_model: NestedModel = NestedModel(value="test")
    optional_nested: NestedModel | None = None

    model_config = {"json_schema_extra": {"description": "Test settings"}}


FieldTestSettings.model_fields["with_desc"].description = "A test description"


class TestFormatField:
    def test_simple_field_has_type(self) -> None:
        field = FieldTestSettings.model_fields["simple"]
        result = ConfigWriter._format_field("simple", field)
        assert "# Type: str" in result
        assert "simple: value" in result

    def test_field_with_description(self) -> None:
        field = FieldTestSettings.model_fields["with_desc"]
        result = ConfigWriter._format_field("with_desc", field)
        assert "# Type: str" in result
        assert "# Description: A test description" in result
        assert "with_desc: test" in result

    def test_optional_field_commented_out(self) -> None:
        field = FieldTestSettings.model_fields["optional_field"]
        result = ConfigWriter._format_field("optional_field", field)
        for line in result.split("\n"):
            assert line.startswith("#")
        assert "# optional_field: null" in result

    def test_required_field_warning(self) -> None:
        field = FieldTestSettings.model_fields["required_field"]
        result = ConfigWriter._format_field("required_field", field)
        assert "# REQUIRED - you must set this value" in result
        assert "required_field: " in result

    def test_sensitive_field_warning(self) -> None:
        field = FieldTestSettings.model_fields["api_key"]
        result = ConfigWriter._format_field("api_key", field)
        assert "# SENSITIVE - do not commit to version control" in result

    def test_required_and_sensitive(self) -> None:
        field = FieldTestSettings.model_fields["password"]
        result = ConfigWriter._format_field("password", field)
        assert "# REQUIRED - you must set this value" in result
        assert "# SENSITIVE - do not commit to version control" in result

    def test_nested_model_field(self) -> None:
        field = FieldTestSettings.model_fields["nested_model"]
        result = ConfigWriter._format_field("nested_model", field)
        assert "# Type: NestedModel" in result
        assert "nested_model:" in result
        assert "  value: test" in result

    def test_optional_nested_model_commented(self) -> None:
        field = FieldTestSettings.model_fields["optional_nested"]
        result = ConfigWriter._format_field("optional_nested", field)
        for line in result.split("\n"):
            assert line.startswith("#")
        assert "# optional_nested:" in result
        assert "#   value:" in result


class TestWrite:
    def test_write_to_new_file(self, tmp_path: Path) -> None:
        output = tmp_path / "config.yaml"
        ConfigWriter.write(GenerateTestSettings, output, "myapp")
        assert output.exists()
        content = output.read_text()
        assert "# Configuration for myapp" in content
        assert "max_retries:" in content

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "config.yaml"
        ConfigWriter.write(GenerateTestSettings, nested, "myapp")
        assert nested.exists()
        assert nested.parent.exists()

    def test_write_existing_file_raises(self, tmp_path: Path) -> None:
        existing = tmp_path / "config.yaml"
        existing.write_text("old")
        with pytest.raises(FileExistsError, match="already exists"):
            ConfigWriter.write(GenerateTestSettings, existing, "myapp")

    def test_write_no_extension_works(self, tmp_path: Path) -> None:
        output = tmp_path / "config"
        ConfigWriter.write(GenerateTestSettings, output, "myapp")
        assert output.exists()
        content = output.read_text()
        assert "# Configuration for myapp" in content

    def test_write_resolves_symlink_path(self, tmp_path: Path) -> None:
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        link = tmp_path / "link"
        link.symlink_to(subdir)
        output = link / "config.yaml"
        ConfigWriter.write(GenerateTestSettings, output, "test")
        assert (subdir / "config.yaml").exists()


class BaseAppSettings(BaseModel):
    app_name: str = "base"


class ChildSettings(BaseAppSettings):
    extra_field: str = "child"


class LiteralSettings(BaseModel):
    log_level: Literal["DEBUG", "INFO", "WARN"] = "INFO"


class OrderedSettings(BaseModel):
    first: str = "1"
    second: str = "2"
    third: str = "3"


class GenerateTestSettings(BaseModel):
    api_key: str | None = None
    max_retries: int = 3
    debug: bool = False


class TestGenerate:
    def test_header_contains_command_name(self) -> None:
        result = ConfigWriter.generate(GenerateTestSettings, "myapp")
        assert "# Configuration for myapp" in result

    def test_header_contains_generated_notice(self) -> None:
        result = ConfigWriter.generate(GenerateTestSettings, "myapp")
        assert "# Generated by --config-create" in result

    def test_all_fields_present(self) -> None:
        result = ConfigWriter.generate(GenerateTestSettings, "myapp")
        assert "api_key:" in result or "# api_key:" in result
        assert "max_retries:" in result
        assert "debug:" in result

    def test_ends_with_single_newline(self) -> None:
        result = ConfigWriter.generate(GenerateTestSettings, "myapp")
        assert result.endswith("\n")
        assert not result.endswith("\n\n")

    def test_blank_lines_between_fields(self) -> None:
        result = ConfigWriter.generate(GenerateTestSettings, "myapp")
        lines = result.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("# Type:") and i > 0:
                assert lines[i - 1] == "" or lines[i - 1].startswith("#")

    def test_inherited_fields_in_output(self) -> None:
        result = ConfigWriter.generate(ChildSettings, "test")
        assert "app_name:" in result
        assert "extra_field:" in result

    def test_literal_in_generate_output(self) -> None:
        result = ConfigWriter.generate(LiteralSettings, "test")
        assert "one of: 'DEBUG', 'INFO', 'WARN'" in result

    def test_field_order_preserved(self) -> None:
        result = ConfigWriter.generate(OrderedSettings, "test")
        first_pos = result.index("first:")
        second_pos = result.index("second:")
        third_pos = result.index("third:")
        assert first_pos < second_pos < third_pos

    def test_optional_suffix_in_type_comment(self) -> None:
        result = ConfigWriter.generate(GenerateTestSettings, "myapp")
        assert "str | None (optional)" in result

    def test_generated_yaml_is_parseable(self) -> None:
        result = ConfigWriter.generate(GenerateTestSettings, "myapp")
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)
        assert "max_retries" in parsed
        assert "debug" in parsed

    def test_complex_yaml_is_parseable(self) -> None:
        result = ConfigWriter.generate(AppSettings, "test")
        parsed = yaml.safe_load(result)
        assert "database" in parsed
        assert parsed["database"]["host"] == "localhost"


class TestSensitiveFieldInModelInstance:
    def test_sensitive_field_in_default_instance_via_generate(self) -> None:
        result = ConfigWriter.generate(SettingsWithDefaultInstance, "test")
        lines = result.splitlines()
        for idx, line in enumerate(lines):
            if "password:" in line and not line.strip().startswith("#"):
                assert lines[idx - 1].strip() == "# SENSITIVE - do not commit to version control", (
                    f"Expected SENSITIVE comment before password, got: {lines[idx - 1]}"
                )
                break
        else:
            pytest.fail("password field not found in generate output")
