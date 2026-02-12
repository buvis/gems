import click


@click.group(help="CLI tool to manage accounts in foreign currencies")
def cli() -> None:
    pass


@cli.command("balance")
def balance() -> None:
    """Print current balance of all accounts and currencies"""
    from fctracker.commands.balance.balance import CommandBalance

    cmd = CommandBalance()
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
def transactions(account: str = "", currency: str = "", month: str = "") -> None:
    """Print transactions"""
    from fctracker.commands.transactions.transactions import CommandTransactions

    cmd = CommandTransactions(account, currency, month)
    cmd.execute()


if __name__ == "__main__":
    cli()
