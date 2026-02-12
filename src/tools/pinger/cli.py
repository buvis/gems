from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings

from pinger.settings import PingerSettings


@click.group(help="Useful tools around ICMP ping")
def cli() -> None:
    pass


@cli.command("wait", help="Wait for host to be online")
@buvis_options(settings_class=PingerSettings)
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

    from pinger.commands.wait.exceptions import CommandWaitTimeoutError
    from pinger.commands.wait.wait import CommandWait

    cmd = CommandWait(host=host, timeout=resolved_timeout)
    with console.status(f"Waiting for {host} to be online (max {resolved_timeout} seconds)"):
        try:
            cmd.execute()
        except CommandWaitTimeoutError:
            console.panic(f"Timeout reached when waiting for {host}")
    console.success(f"{host} is now online")


if __name__ == "__main__":
    cli()
