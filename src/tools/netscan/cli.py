from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings
from buvis.pybase.result import FatalError

from netscan.settings import NetscanSettings


@click.group(help="Network scanning tools")
@buvis_options(settings_class=NetscanSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("hosts", help="Discover hosts on the local network")
@click.option("-i", "--interface", default=None, help="Network interface to scan.")
@click.pass_context
def hosts(ctx: click.Context, interface: str | None = None) -> None:
    settings = get_settings(ctx, NetscanSettings)
    resolved_interface = interface if interface is not None else settings.interface

    from netscan.commands.hosts.hosts import CommandHosts

    cmd = CommandHosts(interface=resolved_interface)
    try:
        with console.status(f"Scanning {resolved_interface} for hosts"):
            result = cmd.execute()
    except FatalError as e:
        console.panic(str(e))
        return

    for w in result.warnings:
        console.warning(w)
    if result.success:
        console.success(result.output or "Done")
    else:
        console.failure(result.error or "Failed")


@cli.command("ssh", help="Find hosts with SSH available")
@click.option("-i", "--interface", default=None, help="Network interface to scan.")
@click.option("-p", "--port", type=int, default=None, help="SSH port to scan.")
@click.pass_context
def ssh(ctx: click.Context, interface: str | None = None, port: int | None = None) -> None:
    settings = get_settings(ctx, NetscanSettings)
    resolved_interface = interface if interface is not None else settings.interface
    resolved_port = port if port is not None else settings.ssh_port

    from netscan.commands.ssh.ssh import CommandSsh

    cmd = CommandSsh(interface=resolved_interface, port=resolved_port)
    try:
        with console.status(f"Scanning {resolved_interface} for SSH on port {resolved_port}"):
            result = cmd.execute()
    except FatalError as e:
        console.panic(str(e))
        return

    for w in result.warnings:
        console.warning(w)
    if result.success:
        console.success(result.output or "Done")
    else:
        console.failure(result.error or "Failed")


if __name__ == "__main__":
    cli()
