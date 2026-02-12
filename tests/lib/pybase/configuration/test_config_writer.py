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

    def test_literal_type(self) -> None:
        result = ConfigWriter._format_type(Literal["a", "b"])
        assert result == "one of: 'a', 'b'"

    def test_literal_single_value(self) -> None:
        result = ConfigWriter._format_type(Literal["DEBUG"])
        assert result == "one of: 'DEBUG'"

    def test_optional_str(self) -> None:
        result = ConfigWriter._format_type(str | None)
        assert result == "str | None (optional)"

    def test_optional_path(self) -> None:
        result = ConfigWriter._format_type(Path | None)
        assert result == "Path | None (optional)"

    def test_union_typing_module(self) -> None:
        result = ConfigWriter._format_type(Union[str, None])
        assert result == "str | None (optional)"

    def test_union_multiple_types(self) -> None:
        result = ConfigWriter._format_type(int | str)
        assert result == "int | str"

    def test_three_type_union_with_none(self) -> None:
        result = ConfigWriter._format_type(str | int | None)
        assert result == "str | int | None"

    def test_list_str(self) -> None:
        result = ConfigWriter._format_type(list[str])
        assert result == "list[str]"

    def test_dict_str_int(self) -> None:
        result = ConfigWriter._format_type(dict[str, int])
        assert result == "dict[str, int]"

    def test_list_path(self) -> None:
        result = ConfigWriter._format_type(list[Path])
        assert result == "list[Path]"

    def test_simple_str(self) -> None:
        result = ConfigWriter._format_type(str)
        assert result == "str"

    def test_simple_int(self) -> None:
        result = ConfigWriter._format_type(int)
        assert result == "int"

    def test_simple_bool(self) -> None:
        result = ConfigWriter._format_type(bool)
        assert result == "bool"

    def test_simple_path(self) -> None:
        result = ConfigWriter._format_type(Path)
        assert result == "Path"

    def test_basemodel_subclass(self) -> None:
        result = ConfigWriter._format_type(NestedModel)
        assert result == "NestedModel"

    def test_nested_generic(self) -> None:
        result = ConfigWriter._format_type(list[dict[str, int]])
        assert result == "list[dict[str, int]]"

    def test_nonetype_standalone(self) -> None:
        result = ConfigWriter._format_type(type(None))
        assert result == "None"


class TestFormatValue:
    """Tests for ConfigWriter._format_value."""

    def test_none(self) -> None:
        assert ConfigWriter._format_value(None) == "null"

    def test_true(self) -> None:
        assert ConfigWriter._format_value(True) == "true"

    def test_false(self) -> None:
        assert ConfigWriter._format_value(False) == "false"

    def test_simple_string(self) -> None:
        assert ConfigWriter._format_value("simple") == "simple"

    def test_empty_string(self) -> None:
        assert ConfigWriter._format_value("") == '""'

    def test_string_with_colon(self) -> None:
        assert ConfigWriter._format_value("foo:bar") == '"foo:bar"'

    def test_string_with_hash(self) -> None:
        assert ConfigWriter._format_value("has#hash") == '"has#hash"'

    def test_string_with_embedded_double_quote(self) -> None:
        value = 'foo"bar'
        formatted = ConfigWriter._format_value(value)
        assert formatted == '"foo\\"bar"'
        assert yaml.safe_load(formatted) == value

    def test_string_with_backslash(self) -> None:
        value = "foo\\bar"
        formatted = ConfigWriter._format_value(value)
        assert formatted == '"foo\\\\bar"'
        assert yaml.safe_load(formatted) == value

    def test_string_with_backslash_and_quote(self) -> None:
        value = 'foo\\"bar'
        formatted = ConfigWriter._format_value(value)
        assert formatted == '"foo\\\\\\"bar"'
        assert yaml.safe_load(formatted) == value

    def test_string_with_newline(self) -> None:
        value = "line1\nline2"
        formatted = ConfigWriter._format_value(value)
        assert formatted.startswith('"')
        assert yaml.safe_load(formatted) == value

    def test_string_with_carriage_return(self) -> None:
        value = "line1\rline2"
        formatted = ConfigWriter._format_value(value)
        assert formatted.startswith('"')
        assert yaml.safe_load(formatted) == value

    def test_string_with_tab(self) -> None:
        value = "col1\tcol2"
        formatted = ConfigWriter._format_value(value)
        assert formatted.startswith('"')
        assert yaml.safe_load(formatted) == value

    def test_string_with_mixed_whitespace(self) -> None:
        value = "line1\nline2\ttab\rreturn"
        formatted = ConfigWriter._format_value(value)
        assert formatted.startswith('"')
        assert yaml.safe_load(formatted) == value

    def test_path(self) -> None:
        assert ConfigWriter._format_value(Path("/tmp/test")) == "/tmp/test"

    def test_empty_list(self) -> None:
        assert ConfigWriter._format_value([]) == "[]"

    def test_list_strings(self) -> None:
        assert ConfigWriter._format_value(["a", "b"]) == "[a, b]"

    def test_list_with_null(self) -> None:
        assert ConfigWriter._format_value([1, None]) == "[1, null]"

    def test_empty_dict(self) -> None:
        assert ConfigWriter._format_value({}) == "{}"

    def test_dict_simple(self) -> None:
        assert ConfigWriter._format_value({"a": 1}) == "{a: 1}"

    def test_dict_with_bool(self) -> None:
        assert ConfigWriter._format_value({"x": True}) == "{x: true}"

    def test_int(self) -> None:
        assert ConfigWriter._format_value(42) == "42"

    def test_float(self) -> None:
        assert ConfigWriter._format_value(3.14) == "3.14"


class SampleSettings(BaseModel):
    """Sample settings for testing field analysis."""

    required_field: str
    optional_field: str | None = None
    optional_with_default: str = "default"
    nested: NestedModel | None = None
    nested_required: NestedModel
    list_field: list[str] = []


class DbWithPassword(BaseModel):
    """Nested model with sensitive field for instance formatting test."""

    host: str = "localhost"
    password: str = "secret"


class SettingsWithDefaultInstance(BaseModel):
    """Settings with nested model having default instance."""

    db: DbWithPassword = DbWithPassword()


class SimpleInstance(BaseModel):
    """Simple model for instance formatting tests."""

    name: str = "test"
    count: int = 42


class NestedInstanceParent(BaseModel):
    """Parent model containing nested instance."""

    label: str = "parent"
    child: SimpleInstance = SimpleInstance()


class InstanceWithSensitive(BaseModel):
    """Model with sensitive field for instance formatting."""

    host: str = "localhost"
    password: str = "secret123"


class SettingsWithInstanceDefault(BaseModel):
    """Settings with BaseModel instance as default value."""

    app_name: str = "myapp"
    database: InstanceWithSensitive = InstanceWithSensitive()


class TestIsOptional:
    """Tests for ConfigWriter._is_optional."""

    def test_field_with_none_default(self) -> None:
        field = SampleSettings.model_fields["optional_field"]
        assert ConfigWriter._is_optional(field) is True

    def test_field_with_string_default(self) -> None:
        field = SampleSettings.model_fields["optional_with_default"]
        assert ConfigWriter._is_optional(field) is False

    def test_required_field(self) -> None:
        field = SampleSettings.model_fields["required_field"]
        assert ConfigWriter._is_optional(field) is False

    def test_optional_nested_model(self) -> None:
        field = SampleSettings.model_fields["nested"]
        assert ConfigWriter._is_optional(field) is True


class TestIsRequired:
    """Tests for ConfigWriter._is_required."""

    def test_required_field(self) -> None:
        field = SampleSettings.model_fields["required_field"]
        assert ConfigWriter._is_required(field) is True

    def test_field_with_default(self) -> None:
        field = SampleSettings.model_fields["optional_with_default"]
        assert ConfigWriter._is_required(field) is False

    def test_field_with_none_default(self) -> None:
        field = SampleSettings.model_fields["optional_field"]
        assert ConfigWriter._is_required(field) is False

    def test_field_with_default_factory(self) -> None:
        field = SampleSettings.model_fields["list_field"]
        assert ConfigWriter._is_required(field) is False

    def test_nested_required(self) -> None:
        field = SampleSettings.model_fields["nested_required"]
        assert ConfigWriter._is_required(field) is True


class TestIsNestedModel:
    """Tests for ConfigWriter._is_nested_model."""

    def test_basemodel_subclass(self) -> None:
        assert ConfigWriter._is_nested_model(NestedModel) is True

    def test_optional_basemodel(self) -> None:
        assert ConfigWriter._is_nested_model(NestedModel | None) is True

    def test_string_type(self) -> None:
        assert ConfigWriter._is_nested_model(str) is False

    def test_list_type(self) -> None:
        assert ConfigWriter._is_nested_model(list[str]) is False


class TestExtractModelClass:
    """Tests for ConfigWriter._extract_model_class."""

    def test_direct_model(self) -> None:
        result = ConfigWriter._extract_model_class(NestedModel)
        assert result is NestedModel

    def test_optional_model(self) -> None:
        result = ConfigWriter._extract_model_class(NestedModel | None)
        assert result is NestedModel

    def test_non_model_returns_none(self) -> None:
        result = ConfigWriter._extract_model_class(str)
        assert result is None

    def test_list_returns_none(self) -> None:
        result = ConfigWriter._extract_model_class(list[str])
        assert result is None


class DatabaseSettings(BaseModel):
    """Sample database settings for nesting tests."""

    host: str = "localhost"
    port: int = 5432


class AppSettings(BaseModel):
    """Sample app settings with nested model."""

    name: str = "myapp"
    database: DatabaseSettings = DatabaseSettings()


class DeepSettings(BaseModel):
    """Settings with three-level nesting."""

    app: AppSettings = AppSettings()


class NestedWithSensitive(BaseModel):
    host: str = "localhost"
    password: str = "secret"


class TestFormatNestedModel:
    """Tests for ConfigWriter._format_nested_model."""

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
        # required_field has no default, should get empty string
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
    """Tests for ConfigWriter._format_model_instance."""

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
        assert "test" not in result  # default shouldnt appear

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
        """Verify SENSITIVE warning for nested model instance with password."""
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
        """Verify generate() output includes instance values for default BaseModel."""
        result = ConfigWriter.generate(SettingsWithInstanceDefault, "test")
        assert "app_name: myapp" in result
        assert "database:" in result
        assert "  host: localhost" in result
        assert "  password: secret123" in result
        assert "# SENSITIVE" in result


class FieldTestSettings(BaseModel):
    """Settings for testing _format_field."""

    simple: str = "value"
    with_desc: str = "test"
    optional_field: str | None = None
    required_field: str
    api_key: str = "secret"
    password: str
    nested_model: NestedModel = NestedModel(value="test")
    optional_nested: NestedModel | None = None

    model_config = {"json_schema_extra": {"description": "Test settings"}}


# Set description on with_desc field
FieldTestSettings.model_fields["with_desc"].description = "A test description"


class TestFormatField:
    """Tests for ConfigWriter._format_field."""

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
        # All lines should be commented
        for line in result.split("\n"):
            assert line.startswith("#")
        assert "# optional_field: null" in result

    def test_required_field_warning(self) -> None:
        field = FieldTestSettings.model_fields["required_field"]
        result = ConfigWriter._format_field("required_field", field)
        assert "# REQUIRED - you must set this value" in result
        # Value should be empty string
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
        # All lines should be commented
        for line in result.split("\n"):
            assert line.startswith("#")
        assert "# optional_nested:" in result
        assert "#   value:" in result


class TestWrite:
    """Tests for ConfigWriter.write."""

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
        """Verify write() resolves symlinks."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        link = tmp_path / "link"
        link.symlink_to(subdir)
        output = link / "config.yaml"
        ConfigWriter.write(GenerateTestSettings, output, "test")
        assert (subdir / "config.yaml").exists()


class BaseAppSettings(BaseModel):
    """Settings base to verify inherited fields appear."""

    app_name: str = "base"


class ChildSettings(BaseAppSettings):
    """Child settings that should include inherited values in output."""

    extra_field: str = "child"


class LiteralSettings(BaseModel):
    """Settings for ensuring literal choices are described."""

    log_level: Literal["DEBUG", "INFO", "WARN"] = "INFO"


class OrderedSettings(BaseModel):
    """Settings used to verify field order is preserved."""

    first: str = "1"
    second: str = "2"
    third: str = "3"


class GenerateTestSettings(BaseModel):
    """Sample settings for generate tests."""

    api_key: str | None = None
    max_retries: int = 3
    debug: bool = False


class TestGenerate:
    """Tests for ConfigWriter.generate."""

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
        # Should have blank lines between field blocks
        lines = result.split("\n")
        # Find where max_retries starts and check there's a blank line before it
        for i, line in enumerate(lines):
            if line.startswith("# Type:") and i > 0:
                # Check previous line is either blank or part of previous field
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
        """Verify full generate() output parses with yaml.safe_load()."""
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
    """Tests for SENSITIVE warning in _format_model_instance."""

    def test_sensitive_field_in_default_instance_via_generate(self) -> None:
        """Nested model with default instance emits SENSITIVE for password."""
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
