from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings

from pinger.settings import PingerSettings


@click.group(help="Useful tools around ICMP ping")
@buvis_options(settings_class=PingerSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("wait", help="Wait for host to be online")
@click.option(
    "-t",
    "--timeout",
    type=int,
    default=None,
    help="Give up waiting after xxx seconds.",
)
@click.argument("host")
@click.pass_context
def wait(ctx: click.Context, host: str, timeout: int | None = None) -> None:
    settings = get_settings(ctx, PingerSettings)

    # CLI overrides settings
    resolved_timeout = timeout if timeout is not None else settings.wait_timeout

    try:
        from pinger.commands.wait.wait import CommandWait
    except ImportError:
        console.require_import("pinger")
        return

    cmd = CommandWait(host=host, timeout=resolved_timeout)
    with console.status(f"Waiting for {host} to be online (max {resolved_timeout} seconds)"):
        result = cmd.execute()
    if result.success:
        console.success(f"{host} is now online")
    else:
        console.panic(result.error or "Wait failed")


if __name__ == "__main__":
    cli()
