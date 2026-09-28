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


@click.group(
    help="POrtfolio STandUP — collect and render portfolio state.",
    invoke_without_command=True,
)
@buvis_options(settings_class=PostupSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)
    # Bare `postup` (no subcommand) runs the text brief — the default surface.
    # This path pulls in only the pure derive layer, never Textual.
    if ctx.invoked_subcommand is None:
        from postup.commands.brief.brief import CommandBrief

        settings = get_settings(ctx, PostupSettings)
        result = CommandBrief(settings).execute()
        if result.success and result.metadata.get("text"):
            console.print(str(result.metadata["text"]), mode="raw")
        console.report_result(result)


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


@cli.command("enrich", help="Enrich the collected data into epics.json via the claude CLI (optional).")
@click.pass_context
def enrich(ctx: click.Context) -> None:
    """Build the enrichment prompt, invoke claude, and write epics.json."""
    from postup.commands.enrich.enrich import CommandEnrich

    settings = get_settings(ctx, PostupSettings)
    result = CommandEnrich(settings).execute()
    console.report_result(result)


@cli.command("brief", help="Print the deterministic text standup from the latest data.json.")
@click.pass_context
def brief(ctx: click.Context) -> None:
    """Render the text standup (the same surface as bare ``postup``)."""
    from postup.commands.brief.brief import CommandBrief

    settings = get_settings(ctx, PostupSettings)
    result = CommandBrief(settings).execute()
    if result.success and result.metadata.get("text"):
        console.print(str(result.metadata["text"]), mode="raw")
    console.report_result(result)


@cli.command("tui", help="Open the interactive Textual standup (requires the 'postup' extra).")
@click.pass_context
def tui(ctx: click.Context) -> None:
    """Launch the Textual standup; a missing extra yields install guidance."""
    settings = get_settings(ctx, PostupSettings)
    try:
        from postup.commands.tui.tui import CommandTui
    except ImportError:
        console.require_import("postup")
        return
    result = CommandTui(settings).execute()
    console.report_result(result)


@cli.command("serve", help="Start the web dashboard (requires the 'postup-web' extra).")
@click.option("-p", "--port", default=8000, show_default=True, type=int, help="Port to listen on.")
@click.option("-H", "--host", default="127.0.0.1", show_default=True, help="Interface to bind to.")
@click.option("--no-browser", is_flag=True, default=False, help="Do not open the browser on start.")
@click.pass_context
def serve(ctx: click.Context, port: int, host: str, *, no_browser: bool) -> None:
    """Serve the portfolio web UI; a missing web extra yields install guidance."""
    from postup.commands.serve.serve import MISSING_EXTRA_ERROR, CommandServe
    from postup.params.serve import ServeParams

    settings = get_settings(ctx, PostupSettings)
    params = ServeParams(host=host, port=port, no_browser=no_browser)
    result = CommandServe(settings, params).execute()
    if not result.success and result.error == MISSING_EXTRA_ERROR:
        console.require_import("postup-web", tool_name="postup serve")
        return
    console.report_result(result)


if __name__ == "__main__":
    cli()
