import click
from buvis.pybase.configuration import buvis_options, get_settings

from outlookctl.settings import OutlookctlSettings


@click.group(help="CLI to Outlook")
def cli() -> None:
    pass


@cli.command("create_timeblock")
@buvis_options(settings_class=OutlookctlSettings)
@click.pass_context
def create_timeblock(ctx: click.Context) -> None:
    from outlookctl.commands.create_timeblock.create_timeblock import CommandCreateTimeblock

    settings = get_settings(ctx, OutlookctlSettings)
    cmd = CommandCreateTimeblock(duration=settings.default_timeblock_duration)
    cmd.execute()


if __name__ == "__main__":
    cli()
