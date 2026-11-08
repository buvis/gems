from __future__ import annotations

from pathlib import Path

import click
from buvis.pybase.configuration import buvis_options

from bim.doc_cli import register_doc_group
from bim.note_read_cli import register_note_read_commands
from bim.note_write_cli import register_note_write_commands
from bim.serve_cli import register_serve_command
from bim.settings import BimSettings

SKILL_PATH = Path(__file__).with_name("SKILL.md")
_AGENT_EPILOG = "Are you an AI agent? Skip this if a bim skill is already in your context. Otherwise run: bim --skill"


def _print_skill(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Print the bundled agent skill verbatim and exit, like ``herdr --skill``.

    Plain stdout on purpose: agents save or read this payload as a file, and
    console status markers or Rich line wrapping would corrupt it.
    """
    if not value or ctx.resilient_parsing:
        return
    click.echo(SKILL_PATH.read_text(encoding="utf-8"), nl=False)
    ctx.exit(0)


@click.group(help="CLI to BUVIS InfoMesh", epilog=_AGENT_EPILOG)
@click.option(
    "--skill",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_skill,
    help="Print the bundled agent skill (SKILL.md) and exit.",
)
@buvis_options(settings_class=BimSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


register_note_write_commands(cli)
register_note_read_commands(cli)
register_serve_command(cli)
register_doc_group(cli)


if __name__ == "__main__":
    cli()
