"""Click CLI adapter for ``postup``.

The CLI layer inspects the :class:`CommandResult` and renders it through the
buvis ``console`` — command classes never print. Command classes are imported
lazily inside handlers so a bare ``postup --help`` pulls nothing heavy.
"""

from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings

from postup.settings import PostupSettings

__all__ = ["cli"]


@click.group(help="POrtfolio STandUP — collect and render portfolio state.")
@buvis_options(settings_class=PostupSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)


@cli.command("collect", help="Collect portfolio state into the versioned file contracts.")
@click.option("--no-fetch", is_flag=True, help="Skip 'git fetch' before reading each repo.")
@click.option("--days", type=int, default=60, show_default=True, help="Commit window in days.")
@click.pass_context
def collect(ctx: click.Context, *, no_fetch: bool, days: int) -> None:
    """Discover repos, collect their signals, and write the contracts."""
    from postup.commands.collect.collect import CommandCollect

    settings = get_settings(ctx, PostupSettings)
    result = CommandCollect(settings, fetch=not no_fetch, days=days).execute()
    console.report_result(result)


if __name__ == "__main__":
    cli()
