"""Click integration for BUVIS configuration."""

from __future__ import annotations

import contextlib
import functools
import platform
import types
import weakref
import webbrowser
from collections.abc import Callable
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Any, Literal, TypeVar, Union, cast, get_args, get_origin, overload
from urllib.parse import urlencode

import click
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .resolver import ConfigResolver
from .settings import GlobalSettings

F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T", bound="BaseModel")


@overload
def get_settings(ctx: click.Context) -> GlobalSettings: ...


@overload
def get_settings(ctx: click.Context, settings_class: type[T]) -> T: ...


def get_settings(ctx: click.Context, settings_class: type[T] | None = None) -> T | GlobalSettings:
    """Get settings from Click context.

    Args:
        ctx: Click context with settings stored by buvis_options decorator.
        settings_class: Specific settings class to retrieve from context.
            Defaults to GlobalSettings for backward compatibility.

    Raises:
        RuntimeError: If called before buvis_options decorator ran.

    Returns:
        The requested settings instance from context.
    """
    msg = "get_settings() called but buvis_options decorator not applied"

    if ctx.obj is None:
        raise RuntimeError(msg)

    obj = cast(dict[object, object], ctx.obj)
    if settings_class is None:
        # Backward compat: return ctx.obj['settings']
        if "settings" not in obj:
            raise RuntimeError(msg)
        return cast(GlobalSettings, obj["settings"])

    if settings_class not in obj:
        raise RuntimeError(
            f"Settings class {settings_class.__name__} not found. "
            f"Did you use @buvis_options(settings_class={settings_class.__name__})?"
        )
    return cast(T, obj[settings_class])


_BUVIS_META_CHECKED_KEY = "buvis_update_checked"
_buvis_callbacks: weakref.WeakSet[Callable[..., Any]] = weakref.WeakSet()
_parse_args_patch_installed = False


def _run_force_update_and_exit(ctx: click.Context) -> None:
    """Run a user-initiated update and exit Click with its return code.

    Called from the patched ``Group.parse_args`` when ``--update`` appears in
    argv anywhere (including after a subcommand name). The root-level eager
    option handles plain ``tool --update``; this handles ``tool sub --update``
    where the subcommand would otherwise reject the unknown option.
    """
    from buvis.pybase.updater import force_update

    exit_code = force_update(GlobalSettings())
    ctx.exit(exit_code)


def _run_update_check_once(ctx: click.Context) -> None:
    """Run the auto-update check at most once per root invocation."""
    root = ctx.find_root()
    if root.meta.get(_BUVIS_META_CHECKED_KEY):
        return
    root.meta[_BUVIS_META_CHECKED_KEY] = True

    with contextlib.suppress(Exception):
        from buvis.pybase.updater import check_and_update

        check_and_update(GlobalSettings())


def _install_parse_args_patch() -> None:
    """Patch ``click.Command.parse_args`` and ``click.Group.parse_args`` to run the update
    check before any eager callbacks (``--version``, ``--help``, ``--feedback``, etc.) fire.

    The patch is scoped to commands whose callback was registered via ``buvis_options``, so
    it is a no-op for third-party Click commands in the same process. Idempotent: re-importing
    this module does not stack patches.
    """
    global _parse_args_patch_installed
    if _parse_args_patch_installed:
        return
    _parse_args_patch_installed = True

    original_command_parse_args = click.Command.parse_args
    original_group_parse_args = click.Group.parse_args

    def patched_command_parse_args(self: click.Command, ctx: click.Context, args: list[str]) -> list[str]:
        if self.callback in _buvis_callbacks and "--update" not in args:
            _run_update_check_once(ctx)
        return original_command_parse_args(self, ctx, args)

    def patched_group_parse_args(self: click.Group, ctx: click.Context, args: list[str]) -> list[str]:
        if self.callback in _buvis_callbacks:
            if "--update" in args:
                # Intercept --update anywhere in argv so `tool sub --update` works
                # even though --update is only declared on the root group.
                _run_force_update_and_exit(ctx)
            else:
                _run_update_check_once(ctx)
        return original_group_parse_args(self, ctx, args)

    click.Command.parse_args = patched_command_parse_args  # type: ignore[method-assign]
    click.Group.parse_args = patched_group_parse_args  # type: ignore[method-assign]


_install_parse_args_patch()


def _update_callback(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Force-check PyPI and upgrade if newer version is available, then exit."""
    if not value or ctx.resilient_parsing:
        return

    from buvis.pybase.updater import force_update

    exit_code = force_update(GlobalSettings())
    ctx.exit(exit_code)


def _feedback_callback(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Open feedback form in browser when --feedback is passed."""
    if not value or ctx.resilient_parsing:
        return

    params = urlencode(
        {
            "project": "buvis-gems",
            "tool": ctx.info_name or "unknown",
            "version": pkg_version("buvis-gems"),
            "os": platform.system(),
            "python": platform.python_version(),
        }
    )
    url = f"https://feedback.buvis.net/?{params}"

    if webbrowser.open(url):
        click.echo(f"Opened feedback form: {url}")
    else:
        click.echo(f"Open this URL to submit feedback: {url}")

    ctx.exit(0)


def _create_buvis_options(settings_class: type[T]) -> Callable[[F], F]:
    """Build a decorator that injects settings into the Click context."""

    def decorator(f: F) -> F:
        @click.version_option(
            version=pkg_version("buvis-gems"),
            prog_name="buvis-gems",
        )
        @click.option(
            "--feedback",
            is_flag=True,
            is_eager=True,
            expose_value=False,
            callback=_feedback_callback,
            help="Open feedback form in browser.",
        )
        @click.option(
            "--update",
            is_flag=True,
            is_eager=True,
            expose_value=False,
            callback=_update_callback,
            help="Force-check for updates and upgrade if newer version is available.",
        )
        @click.option(
            "--config",
            type=click.Path(exists=True, dir_okay=False, resolve_path=True),
            help="YAML config file path.",
        )
        @click.option(
            "--config-create",
            type=click.Path(dir_okay=False, resolve_path=True),
            help="Generate YAML config template to FILE.",
        )
        @click.option(
            "--config-dir",
            type=click.Path(exists=True, file_okay=False, resolve_path=True),
            help="Configuration directory.",
        )
        @click.option(
            "--log-level",
            type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
            default=None,
            help="Logging level.",
        )
        @click.option(
            "--debug/--no-debug",
            default=None,
            help="Enable debug mode.",
        )
        @click.pass_context
        @functools.wraps(f)
        def wrapper(  # noqa: PLR0913  # receives all buvis_options Click params
            ctx: click.Context,
            debug: bool | None,
            log_level: str | None,
            config_dir: str | None,
            config_create: str | None,
            config: str | None,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            if config_create:
                from .config_writer import ConfigWriter

                output = Path(config_create)
                cmd_name = ctx.info_name or "unknown"
                try:
                    ConfigWriter.write(settings_class, output, cmd_name)
                    click.echo(f"Config written to {output}")
                except FileExistsError as e:
                    raise click.ClickException(str(e)) from e
                ctx.exit(0)

            cli_overrides = {k: v for k, v in {"debug": debug, "log_level": log_level}.items() if v is not None}

            resolver = ConfigResolver()
            settings = resolver.resolve(
                settings_class,  # type: ignore[type-var]
                config_dir=config_dir,
                config_path=Path(config) if config else None,
                cli_overrides=cli_overrides,
            )

            ctx.ensure_object(dict)
            ctx.obj[settings_class] = settings
            if settings_class is GlobalSettings:
                ctx.obj["settings"] = settings

            return ctx.invoke(f, *args, **kwargs)

        _buvis_callbacks.add(wrapper)
        return wrapper  # type: ignore[return-value]

    return decorator


@overload
def buvis_options(func: F) -> F: ...


@overload
def buvis_options(
    settings_class_or_func: type[T] | None = ...,
    *,
    settings_class: type[T] | None = ...,
) -> Callable[[F], F]: ...


def buvis_options(  # type: ignore[misc]
    settings_class_or_func: type[T] | F | None = None,
    *,
    settings_class: type[T] | None = None,
) -> Callable[[F], F] | F:
    """Add standard BUVIS options to a Click command.

    Adds ``--version``, ``--feedback``, ``--update``, ``--debug/--no-debug``,
    ``--log-level``, ``--config-dir``, ``--config``, and
    ``--config-create`` options. Resolves settings using ConfigResolver
    and injects into Click context.
    Can be applied as ``@buvis_options``, ``@buvis_options()``, or
    ``@buvis_options(settings_class=CustomSettings)``.

    Example::

        @click.command()
        @buvis_options(settings_class=GlobalSettings)
        @click.pass_context
        def cli(ctx):
            settings = ctx.obj["settings"]
            if settings.debug:
                click.echo("Debug mode enabled")
    """

    if callable(settings_class_or_func) and not isinstance(settings_class_or_func, type):
        return _create_buvis_options(GlobalSettings)(settings_class_or_func)

    if settings_class is not None:
        chosen_settings_class: type[T] = settings_class
    elif isinstance(settings_class_or_func, type):
        chosen_settings_class = settings_class_or_func
    else:
        chosen_settings_class = GlobalSettings  # type: ignore[assignment]

    return _create_buvis_options(chosen_settings_class)


# --- Click option generation from Pydantic models ---


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
