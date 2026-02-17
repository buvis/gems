from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings
from buvis.pybase.result import FatalError

from zseq.settings import ZseqSettings


@click.group(
    help="CLI tool to work with Zettelkasten sequential file naming",
    invoke_without_command=True,
)
@buvis_options(settings_class=ZseqSettings)
@click.option(
    "-p",
    "--path",
    default=None,
    help="Path to directory containing files following Zettelkasten sequential file naming.",
)
@click.option(
    "-m",
    "--misnamed-reporting",
    is_flag=True,
    show_default=True,
    default=False,
    help="Report files not following Zettelkasten sequential file naming",
)
@click.pass_context
def cli(
    ctx: click.Context,
    path: str | None = None,
    *,
    misnamed_reporting: bool = False,
) -> None:
    settings = get_settings(ctx, ZseqSettings)

    # CLI overrides settings
    resolved_path = path if path is not None else settings.path_dir
    resolved_misnamed = misnamed_reporting or settings.is_reporting_misnamed

    from zseq.commands.get_last.get_last import CommandGetLast

    try:
        cmd = CommandGetLast(path_dir=resolved_path, is_reporting_misnamed=resolved_misnamed)
        result = cmd.execute()
    except (ValueError, FatalError) as exc:
        console.panic(str(exc))
        return

    for w in result.warnings:
        console.warning(w)
    if result.success:
        console.success(result.output or "Done")
    else:
        console.failure(result.error or "Failed")


if __name__ == "__main__":
    cli()
