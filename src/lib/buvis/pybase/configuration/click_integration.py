"""Click integration for BUVIS configuration."""

from __future__ import annotations

import functools
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

import click

from .resolver import ConfigResolver
from .settings import GlobalSettings

if TYPE_CHECKING:
    from pydantic import BaseModel


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


def _create_buvis_options(settings_class: type[T]) -> Callable[[F], F]:
    """Build a decorator that injects settings into the Click context."""

    def decorator(f: F) -> F:
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
            type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
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
        def wrapper(
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

    Adds ``--debug/--no-debug``, ``--log-level``, ``--config-dir``, and
    ``--config`` options. Resolves settings using ConfigResolver and
    injects into Click context.
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
