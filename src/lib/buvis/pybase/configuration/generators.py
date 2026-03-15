from __future__ import annotations

import types
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

import click
from pydantic import BaseModel
from pydantic.fields import FieldInfo


def generate_click_options(model: type[BaseModel]) -> list[Callable[..., Any]]:
    """Generate Click option decorators from a Pydantic model's fields.

    Skips 'paths' field (handled as click.argument separately).
    """
    options = []
    for name, field in model.model_fields.items():
        if name == "paths":
            continue
        opt = _field_to_option(name, field)
        if opt is not None:
            options.append(opt)
    return options


def apply_generated_options(model: type[BaseModel]) -> Callable[..., Any]:
    """Decorator that applies generated Click options to a command function."""

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        for opt in reversed(generate_click_options(model)):
            f = opt(f)
        return f

    return decorator


def _unwrap_optional(annotation: type) -> tuple[type, bool]:
    """Unwrap Optional[X] / X | None to (X, True). Non-optional returns (annotation, False)."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return annotation, False


def _apply_bool_optional(name: str, field: FieldInfo, **_: Any) -> Callable[..., Any]:
    pos = f"--{name.replace('_', '-')}"
    neg = f"--no-{name.replace('_', '-')}"
    return click.option(pos + "/" + neg, default=None, help=field.description)


def _apply_bool(kwargs: dict[str, Any], field: FieldInfo, args: list[str], param_name: str) -> Callable[..., Any]:
    kwargs["is_flag"] = True
    kwargs["show_default"] = True
    kwargs["default"] = field.default if field.default is not False else False
    return click.option(*args, param_name, **kwargs)


def _apply_literal(kwargs: dict[str, Any], inner: Any, args: list[str], param_name: str) -> Callable[..., Any]:
    kwargs["type"] = click.Choice(list(get_args(inner)))
    return click.option(*args, param_name, **kwargs)


def _apply_path(kwargs: dict[str, Any], extra: dict[str, Any], args: list[str], param_name: str) -> Callable[..., Any]:
    path_kwargs: dict[str, Any] = {}
    for key, click_key in (("path_exists", "exists"), ("path_file_okay", "file_okay"), ("path_dir_okay", "dir_okay")):
        if key in extra:
            path_kwargs[click_key] = extra[key]
    path_kwargs["resolve_path"] = extra.get("path_resolve", False)
    kwargs["type"] = click.Path(path_type=Path, **path_kwargs)
    return click.option(*args, param_name, **kwargs)


def _field_to_option(name: str, field: FieldInfo) -> Callable[..., Any] | None:
    """Convert a single Pydantic field to a click.option decorator."""
    raw_extra = field.json_schema_extra
    extra: dict[str, Any] = raw_extra if isinstance(raw_extra, dict) else {}
    if extra.get("cli_skip"):
        return None
    short = str(extra["cli_short"]) if "cli_short" in extra else None
    long_name = str(extra.get("cli_long", f"--{name.replace('_', '-')}"))
    param_name = str(extra.get("cli_param", name))

    args: list[str] = [long_name]
    if short:
        args.insert(0, short)

    kwargs: dict[str, Any] = {
        "help": field.description,
        "default": field.default if field.default is not None else None,
    }

    annotation = field.annotation
    if annotation is not None:
        inner, is_optional = _unwrap_optional(annotation)

        if inner is bool and is_optional:
            return _apply_bool_optional(name, field)
        if inner is bool:
            return _apply_bool(kwargs, field, args, param_name)
        if get_origin(inner) is Literal:
            return _apply_literal(kwargs, inner, args, param_name)
        if inner is Path:
            return _apply_path(kwargs, extra, args, param_name)
        if inner is int:
            kwargs["type"] = click.INT

    # Default: string
    return click.option(*args, param_name, **kwargs)
