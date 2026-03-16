"""Generate YAML config templates from pydantic settings classes."""

from __future__ import annotations

import types
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Union, cast, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from .validators import is_sensitive_field


def _format_literal(annotation: Any) -> str:
    values = get_args(annotation)
    formatted = ", ".join(f"'{v}'" for v in values)
    return f"one of: {formatted}"


def _format_union(annotation: Any, format_type: Callable[[Any], str]) -> str:
    args = get_args(annotation)
    non_none = [a for a in args if a is not type(None)]
    if len(non_none) == 1 and type(None) in args:
        return f"{format_type(non_none[0])} | None (optional)"
    return " | ".join(format_type(a) for a in args)


def _format_generic(annotation: Any, origin: Any, format_type: Callable[[Any], str]) -> str:
    args = get_args(annotation)
    if args:
        formatted_args = ", ".join(format_type(a) for a in args)
        return f"{origin.__name__!s}[{formatted_args}]"
    return str(origin.__name__)


_VALUE_FORMATTERS: dict[type, Callable[[Any], str]] = {
    bool: lambda v: "true" if v else "false",
    Path: str,
}


def _format_str_value(value: str) -> str:
    special_chars = ":{}[]#&*!|>'\"%@`\\\n\r\t"
    if not value or any(c in value for c in special_chars):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        escaped = escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return f'"{escaped}"'
    return value


def _format_collection_value(value: list[Any] | tuple[Any, ...], format_value: Callable[[Any], str]) -> str:
    if not value:
        return "[]"
    items = ", ".join(format_value(v) for v in value)
    return f"[{items}]"


def _format_dict_value(value: dict[str, Any], format_value: Callable[[Any], str]) -> str:
    if not value:
        return "{}"
    items = ", ".join(f"{k}: {format_value(v)}" for k, v in value.items())
    return "{" + items + "}"


class ConfigWriter:
    """Generate YAML config templates from pydantic settings classes.

    Provides static methods to introspect pydantic-settings models and
    generate documented YAML configuration templates. Follows the static
    utility class pattern used by StringOperator.

    Example:
        >>> from buvis.pybase.configuration import ConfigWriter
        >>> ConfigWriter.write(MySettings, Path('config.yaml'), 'mytool')
    """

    @staticmethod
    def _format_type(annotation: Any) -> str:
        """Format type annotation for YAML comment.

        Args:
            annotation: Type annotation to format.

        Returns:
            Human-readable type string.
        """
        origin = get_origin(annotation)

        if origin is Literal:
            return _format_literal(annotation)
        if origin in (Union, types.UnionType):
            return _format_union(annotation, ConfigWriter._format_type)
        if origin is not None:
            return _format_generic(annotation, origin, ConfigWriter._format_type)
        if annotation is type(None):
            return "None"
        if hasattr(annotation, "__name__"):
            return str(annotation.__name__)
        return str(annotation)

    @staticmethod
    def _format_value(value: Any) -> str:
        """Format value for YAML output.

        Args:
            value: Value to format.

        Returns:
            YAML-formatted value string.
        """
        if value is None:
            return "null"
        # Check exact type match first (bool before int)
        formatter = _VALUE_FORMATTERS.get(type(value))
        if formatter is not None:
            return formatter(value)
        if isinstance(value, str):
            return _format_str_value(value)
        if isinstance(value, list | tuple):
            return _format_collection_value(value, ConfigWriter._format_value)
        if isinstance(value, dict):
            return _format_dict_value(value, ConfigWriter._format_value)
        return str(value)

    @staticmethod
    def _is_optional(field_info: FieldInfo) -> bool:
        """Check if field allows None.

        Args:
            field_info: Pydantic field info.

        Returns:
            True if field has None default or type includes None.
        """
        if field_info.default is None:
            return True
        annotation = field_info.annotation
        origin = get_origin(annotation)
        if origin in (Union, types.UnionType):
            return type(None) in get_args(annotation)
        return False

    @staticmethod
    def _is_required(field_info: FieldInfo) -> bool:
        """Check if field has no default.

        Args:
            field_info: Pydantic field info.

        Returns:
            True if field has no default value.
        """
        return field_info.default is PydanticUndefined and field_info.default_factory is None

    @staticmethod
    def _is_nested_model(annotation: Any) -> bool:
        """Check if annotation is a BaseModel subclass.

        Args:
            annotation: Type annotation.

        Returns:
            True if annotation is a BaseModel subclass.
        """
        origin = get_origin(annotation)
        if origin in (Union, types.UnionType):
            args = [a for a in get_args(annotation) if a is not type(None)]
            if len(args) == 1:
                return ConfigWriter._is_nested_model(args[0])
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return True
        return False

    @staticmethod
    def _extract_model_class(annotation: Any) -> type[BaseModel] | None:
        """Extract BaseModel class from annotation.

        Args:
            annotation: Type annotation.

        Returns:
            BaseModel subclass or None.
        """
        origin = get_origin(annotation)
        if origin in (Union, types.UnionType):
            args = [a for a in get_args(annotation) if a is not type(None)]
            if len(args) == 1:
                return ConfigWriter._extract_model_class(args[0])
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return annotation
        return None

    @staticmethod
    def _format_nested_model(model_class: type[BaseModel], indent: int = 2) -> str:
        """Format nested BaseModel as YAML (no comments on nested fields).

        Args:
            model_class: The Pydantic BaseModel class to format.
            indent: Current indentation level in spaces.

        Returns:
            YAML-formatted string of the model fields.
        """
        lines: list[str] = []
        prefix = " " * indent

        for name, field_info in model_class.model_fields.items():
            if is_sensitive_field(name):
                lines.append(f"{prefix}# SENSITIVE - do not commit to version control")
            # Get default value
            if field_info.default is not PydanticUndefined:
                value = field_info.default
            elif field_info.default_factory is not None:
                default_factory = cast(Callable[[], Any], field_info.default_factory)
                value = default_factory()
            else:
                value = ""  # Required field gets empty string

            # Check for deeper nesting
            if ConfigWriter._is_nested_model(field_info.annotation):
                nested_class = ConfigWriter._extract_model_class(field_info.annotation)
                if nested_class:
                    lines.append(f"{prefix}{name}:")
                    lines.append(ConfigWriter._format_nested_model(nested_class, indent + 2))
                    continue

            formatted_value = ConfigWriter._format_value(value)
            lines.append(f"{prefix}{name}: {formatted_value}")

        return "\n".join(lines)

    @staticmethod
    def _format_model_instance(instance: BaseModel, indent: int = 2) -> str:
        """Format BaseModel instance as YAML.

        Args:
            instance: The Pydantic BaseModel instance to format.
            indent: Current indentation level in spaces.

        Returns:
            YAML-formatted string of the instance fields.
        """
        lines: list[str] = []
        prefix = " " * indent

        for name in type(instance).model_fields:
            if is_sensitive_field(name):
                lines.append(f"{prefix}# SENSITIVE - do not commit to version control")

            value = getattr(instance, name)

            # Check for deeper nesting
            if isinstance(value, BaseModel):
                lines.append(f"{prefix}{name}:")
                lines.append(ConfigWriter._format_model_instance(value, indent + 2))
                continue

            formatted_value = ConfigWriter._format_value(value)
            lines.append(f"{prefix}{name}: {formatted_value}")

        return "\n".join(lines)

    @staticmethod
    def _get_field_default(field_info: FieldInfo) -> Any:
        """Get default value for a field."""
        if field_info.default is not PydanticUndefined:
            return field_info.default
        if field_info.default_factory is not None:
            return cast(Callable[[], Any], field_info.default_factory)()
        return ""

    @staticmethod
    def _build_comment_lines(name: str, field_info: FieldInfo) -> list[str]:
        """Build type/description/warning comment lines for a field."""
        lines = [f"# Type: {ConfigWriter._format_type(field_info.annotation)}"]
        if field_info.description:
            lines.append(f"# Description: {field_info.description}")
        if ConfigWriter._is_required(field_info):
            lines.append("# REQUIRED - you must set this value")
        if is_sensitive_field(name):
            lines.append("# SENSITIVE - do not commit to version control")
        return lines

    @staticmethod
    def _format_nested_field(
        name: str,
        lines: list[str],
        value: Any,
        is_optional: bool,
        nested_class: type[BaseModel],
    ) -> str:
        """Format a nested model field."""
        if is_optional and value is None:
            lines = ["# " + line for line in lines]
            lines.append(f"# {name}:")
            for nested_line in ConfigWriter._format_nested_model(nested_class).split("\n"):
                lines.append(f"# {nested_line}")
        elif isinstance(value, BaseModel):
            lines.append(f"{name}:")
            lines.append(ConfigWriter._format_model_instance(value))
        else:
            lines.append(f"{name}:")
            lines.append(ConfigWriter._format_nested_model(nested_class))
        return "\n".join(lines)

    @staticmethod
    def _format_field(name: str, field_info: FieldInfo) -> str:
        """Format field with comments for YAML output."""
        lines = ConfigWriter._build_comment_lines(name, field_info)
        is_optional = ConfigWriter._is_optional(field_info)
        value = ConfigWriter._get_field_default(field_info)

        nested_class = ConfigWriter._extract_model_class(field_info.annotation)
        if nested_class and ConfigWriter._is_nested_model(field_info.annotation):
            return ConfigWriter._format_nested_field(name, lines, value, is_optional, nested_class)

        formatted_value = ConfigWriter._format_value(value)
        if is_optional and value is None:
            lines = ["# " + line for line in lines]
            lines.append(f"# {name}: null")
        else:
            lines.append(f"{name}: {formatted_value}")

        return "\n".join(lines)

    @staticmethod
    def write(settings_class: type[BaseModel], output_path: Path, command_name: str) -> None:
        """Write YAML config template to file.

        Args:
            settings_class: The Pydantic BaseModel class to introspect.
            output_path: Destination path for the YAML file.
            command_name: Name used in YAML header comment.

        Raises:
            FileExistsError: If output_path already exists.
        """
        resolved_path = output_path.resolve()

        if resolved_path.exists():
            raise FileExistsError(f"File already exists: {resolved_path}")

        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        content = ConfigWriter.generate(settings_class, command_name)
        resolved_path.write_text(content, encoding="utf-8")

    @staticmethod
    def generate(settings_class: type[BaseModel], command_name: str) -> str:
        """Generate YAML config string.

        Args:
            settings_class: The Pydantic BaseModel class to introspect.
            command_name: Name used in YAML header comment.

        Returns:
            YAML config template as string.
        """
        lines = [
            f"# Configuration for {command_name}",
            "# Generated by --config-create",
            "",
        ]

        for name, field_info in settings_class.model_fields.items():
            field_yaml = ConfigWriter._format_field(name, field_info)
            lines.append(field_yaml)
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"
