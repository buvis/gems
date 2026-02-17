from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings
from rich.table import Table

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
    try:
        cmd = CommandBalance(settings.foreign_currencies, settings.local_currency)
        result = cmd.execute()
    except FileNotFoundError as exc:
        console.panic(str(exc))
        return

    for account in result.metadata.get("accounts", []):
        console.console.print(account)


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
    try:
        cmd = CommandTransactions(settings.foreign_currencies, settings.local_currency, account, currency, month)
        result = cmd.execute()
    except FileNotFoundError as exc:
        console.panic(str(exc))
        return

    for table_data in result.metadata.get("tables", []):
        table = Table(
            show_header=True,
            header_style="bold #268bd2",
            show_lines=True,
            title=table_data["title"],
        )
        table.add_column("Seq.", style="italic #6c71c4")
        table.add_column("Date", style="bold #839496")
        table.add_column("Description")
        table.add_column("Amount", justify="right", style="bold #2aa198")
        table.add_column("Rate", justify="right", style="italic")
        table.add_column("Outflow", justify="right", style="bold #dc322f")
        table.add_column("Inflow", justify="right", style="bold #859900")

        for row in table_data["rows"]:
            table.add_row(
                row["seq"],
                row["date"],
                row["description"],
                row["amount"],
                row["rate"],
                row["outflow"],
                row["inflow"],
            )
        console.console.print(table)
        console.nl()


if __name__ == "__main__":
    cli()
