"""Validation helpers for configuration models."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from typing import Any, Protocol, cast, get_args, get_origin

from pydantic import BaseModel, model_validator

_SENSITIVE_PATTERNS = re.compile(
    r"(authorization|api[_-]?key|secret|token|password|bearer|credential)",
    re.IGNORECASE,
)


class _ModelFieldsOwner(Protocol):
    model_fields: dict[str, Any]


def is_sensitive_field(field_path: str) -> bool:
    """Check if field path contains sensitive data indicators.

    Args:
        field_path: Dotted field path (e.g., "database.password").

    Returns:
        True if any part matches sensitive patterns.
    """
    return bool(_SENSITIVE_PATTERNS.search(field_path))


MAX_NESTING_DEPTH = 5
MAX_JSON_ENV_SIZE = 64 * 1024


def _iter_model_types(annotation: Any) -> Iterator[type[BaseModel]]:
    """Yield BaseModel subclasses that appear in the provided annotation."""
    stack = [annotation]
    seen: set[type[BaseModel]] = set()

    while stack:
        current = stack.pop()

        if isinstance(current, type):
            if issubclass(current, BaseModel) and current not in seen:
                seen.add(current)
                yield current
            continue

        origin = get_origin(current)
        if origin is None:
            continue

        stack.extend(get_args(current))


def get_model_depth(model_class: type[BaseModel], current_depth: int = 0) -> int:
    """Calculate the maximum nesting depth of a Pydantic model.

    The function traverses nested BaseModel fields to find the deepest path
    and short-circuits once the depth exceeds ``MAX_NESTING_DEPTH + 1``.

    Args:
        model_class: The root Pydantic model class to examine.
        current_depth: The depth of the current model in the recursion tree.

    Returns:
        int: The maximum nesting depth encountered relative to the root model.
    """
    if current_depth >= MAX_NESTING_DEPTH + 1:
        return current_depth

    max_depth = current_depth
    for field in model_class.model_fields.values():
        for nested_model in _iter_model_types(field.annotation):
            nested_depth = get_model_depth(nested_model, current_depth + 1)
            max_depth = max(max_depth, nested_depth)

            if max_depth >= MAX_NESTING_DEPTH + 1:
                return max_depth

    return max_depth


def validate_nesting_depth(model_class: type[BaseModel]) -> None:
    """Validate that a model does not exceed the allowed nesting depth.

    Args:
        model_class: The Pydantic model class to validate.

    Raises:
        ValueError: If the model's nesting depth exceeds ``MAX_NESTING_DEPTH``.
    """
    depth = get_model_depth(model_class)
    if depth > MAX_NESTING_DEPTH:
        raise ValueError(f"{model_class.__name__} exceeds max nesting depth {MAX_NESTING_DEPTH} (found depth={depth}).")


def validate_json_env_size(env_var_name: str) -> None:
    """Validate that an environment variable's JSON payload fits within limits.

    Args:
        env_var_name: The name of the environment variable containing JSON data.

    Raises:
        ValueError: If the variable contains more than ``MAX_JSON_ENV_SIZE`` bytes.
    """

    env_value = os.getenv(env_var_name)
    if env_value is None:
        return

    byte_length = len(env_value.encode("utf-8"))
    if byte_length > MAX_JSON_ENV_SIZE:
        raise ValueError(f"{env_var_name} exceeds max JSON size {MAX_JSON_ENV_SIZE} bytes (found {byte_length} bytes).")


class SecureSettingsMixin:
    """Mixin adding security validations for settings.

    Validates:

    - JSON env values don't exceed 64KB
    - Complex types come from validated JSON, not eval()

    Example::

        class MySettings(SecureSettingsMixin, BaseSettings):
            ...
    """

    @model_validator(mode="before")
    @classmethod
    def validate_json_sizes(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Check env var sizes before parsing.

        Args:
            data: Input data dict from pydantic.

        Returns:
            Unmodified data dict if all validations pass.

        Raises:
            ValueError: If any prefixed env var exceeds MAX_JSON_ENV_SIZE.
        """
        config = getattr(cls, "model_config", {})
        prefix = config.get("env_prefix", "")

        for key in os.environ:
            if key.startswith(prefix):
                validate_json_env_size(key)

        return data


class SafeLoggingMixin:
    """Mixin that sanitizes sensitive values in __repr__.

    Per PRD: "Sanitize before logging: Don't log raw JSON (may contain secrets)"

    Masks values for fields whose names match sensitive patterns like
    'api_key', 'password', 'token', 'authorization', etc.
    """

    def __repr__(self) -> str:
        """Repr with sensitive values masked."""
        fields = []
        model_fields = cast(_ModelFieldsOwner, self.__class__).model_fields
        for name in model_fields:
            value = getattr(self, name, None)
            if _SENSITIVE_PATTERNS.search(name):
                fields.append(f"{name}='***'")
            elif isinstance(value, dict):
                safe_dict = {k: "***" if _SENSITIVE_PATTERNS.search(str(k)) else v for k, v in value.items()}
                fields.append(f"{name}={safe_dict}")
            else:
                fields.append(f"{name}={value!r}")
        return f"{self.__class__.__name__}({', '.join(fields)})"
