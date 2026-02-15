from __future__ import annotations

import click
from buvis.pybase.configuration import buvis_options, get_settings

from fctracker.settings import FctrackerSettings


@click.group(help="CLI tool to manage accounts in foreign currencies")
@buvis_options(settings_class=FctrackerSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)


@cli.command("balance")
@click.pass_context
def balance(ctx: click.Context) -> None:
    """Print current balance of all accounts and currencies"""
    from fctracker.commands.balance.balance import CommandBalance

    settings = get_settings(ctx, FctrackerSettings)
    cmd = CommandBalance(settings.foreign_currencies, settings.local_currency)
    cmd.execute()


@cli.command("transactions")
@click.option(
    "-a",
    "--account",
    default="",
    help="Only print transactions for given account",
)
@click.option(
    "-c",
    "--currency",
    default="",
    help="Only print transactions for given currency",
)
@click.option(
    "-m",
    "--month",
    default="",
    help="Only print transactions for given month [YYYY-MM]",
)
@click.pass_context
def transactions(ctx: click.Context, account: str = "", currency: str = "", month: str = "") -> None:
    """Print transactions"""
    from fctracker.commands.transactions.transactions import CommandTransactions

    settings = get_settings(ctx, FctrackerSettings)
    cmd = CommandTransactions(settings.foreign_currencies, settings.local_currency, account, currency, month)
    cmd.execute()


if __name__ == "__main__":
    cli()
