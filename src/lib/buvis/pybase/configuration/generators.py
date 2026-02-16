from __future__ import annotations

import types
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

import click
from pydantic import BaseModel
from pydantic.fields import FieldInfo


def generate_click_options(model: type[BaseModel]) -> list:
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


def apply_generated_options(model: type[BaseModel]):
    """Decorator that applies generated Click options to a command function."""
    def decorator(f):
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


def _field_to_option(name: str, field: FieldInfo):
    """Convert a single Pydantic field to a click.option decorator."""
    extra = field.json_schema_extra or {}
    if extra.get("cli_skip"):
        return None
    short = extra.get("cli_short")
    long_name = extra.get("cli_long", f"--{name.replace('_', '-')}")
    param_name = extra.get("cli_param", name)

    args = [long_name]
    if short:
        args.insert(0, short)

    kwargs: dict[str, Any] = {
        "help": field.description,
        "default": field.default if field.default is not None else None,
    }

    annotation = field.annotation
    inner, is_optional = _unwrap_optional(annotation)

    # bool | None -> --flag/--no-flag with default None
    if inner is bool and is_optional:
        pos = f"--{name.replace('_', '-')}"
        neg = f"--no-{name.replace('_', '-')}"
        return click.option(pos + "/" + neg, default=None, help=field.description)

    # bool -> is_flag
    if inner is bool:
        kwargs["is_flag"] = True
        kwargs["show_default"] = True
        kwargs["default"] = field.default if field.default is not False else False
        return click.option(*args, param_name, **kwargs)

    # Literal -> Choice
    if get_origin(inner) is Literal:
        kwargs["type"] = click.Choice(list(get_args(inner)))
        return click.option(*args, param_name, **kwargs)

    # Path with validation hints from json_schema_extra
    if inner is Path:
        path_kwargs = {}
        if "path_exists" in extra:
            path_kwargs["exists"] = extra["path_exists"]
        if "path_file_okay" in extra:
            path_kwargs["file_okay"] = extra["path_file_okay"]
        if "path_dir_okay" in extra:
            path_kwargs["dir_okay"] = extra["path_dir_okay"]
        path_kwargs["resolve_path"] = extra.get("path_resolve", False)
        kwargs["type"] = click.Path(path_type=Path, **path_kwargs)
        return click.option(*args, param_name, **kwargs)

    # int
    if inner is int:
        kwargs["type"] = click.INT
        return click.option(*args, param_name, **kwargs)

    # Default: string
    return click.option(*args, param_name, **kwargs)
