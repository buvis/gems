from __future__ import annotations

import click
from buvis.pybase.configuration import buvis_options

from bim.doc_cli import register_doc_group
from bim.note_read_cli import register_note_read_commands
from bim.note_write_cli import register_note_write_commands
from bim.serve_cli import register_serve_command
from bim.settings import BimSettings


@click.group(help="CLI to BUVIS InfoMesh")
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
