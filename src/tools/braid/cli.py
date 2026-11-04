from __future__ import annotations

from pathlib import Path

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings
from rich.markup import escape

from braid.settings import BraidSettings


@click.command(help="Compose Agent Skills from multiple repositories and project them to hosts.")
@click.option("--dry-run", is_flag=True, help="report changes without writing")
@click.option("--check", is_flag=True, help="exit non-zero when links, resources or state drift")
@click.option(
    "--source",
    "sources",
    multiple=True,
    type=click.Path(path_type=Path),
    help="additional repository root or skills directory (repeatable)",
)
@click.option(
    "--policy",
    "policies",
    multiple=True,
    type=click.Path(path_type=Path),
    help="additional .braidignore file to load (repeatable)",
)
@click.option(
    "--agents-root",
    type=click.Path(path_type=Path),
    default=None,
    help="override the ~/.agents union root, ahead of BUVIS_BRAID_AGENTS_ROOT",
)
@click.option(
    "--claude-root",
    type=click.Path(path_type=Path),
    default=None,
    help="override the ~/.claude root, ahead of BUVIS_BRAID_CLAUDE_ROOT",
)
@click.option(
    "--config-root",
    type=click.Path(path_type=Path),
    default=None,
    help="override the ~/.config/braid directory holding sources.d, ahead of BUVIS_BRAID_CONFIG_ROOT",
)
@click.option("--no-claude", is_flag=True, help="skip projecting skills into claude-root")
@click.option("--kiro", is_flag=True, help="enroll Kiro once; later runs remember it")
@click.option(
    "--kiro-root",
    type=click.Path(path_type=Path),
    default=None,
    help="enroll a Kiro root (default ~/.kiro), ahead of BUVIS_BRAID_KIRO_ROOT and saved enrollment",
)
@click.option(
    "--kiro-agent",
    "kiro_agents",
    multiple=True,
    metavar="NAME",
    help="enroll an existing <kiro-root>/agents/NAME.json for skill resources (repeatable)",
)
@click.option(
    "--forget-kiro-agent",
    "forget_kiro_agents",
    multiple=True,
    metavar="NAME",
    help="stop managing a custom agent; keep its existing resources (repeatable)",
)
@click.option("--no-kiro", is_flag=True, help="skip Kiro for this run; preserve its links/enrollment")
@buvis_options(settings_class=BraidSettings)
@click.pass_context
def cli(
    ctx: click.Context,
    *,
    dry_run: bool,
    check: bool,
    sources: tuple[Path, ...],
    policies: tuple[Path, ...],
    agents_root: Path | None,
    claude_root: Path | None,
    config_root: Path | None,
    no_claude: bool,
    kiro: bool,
    kiro_root: Path | None,
    kiro_agents: tuple[str, ...],
    forget_kiro_agents: tuple[str, ...],
    no_kiro: bool,
) -> None:
    if dry_run and check:
        console.failure("--dry-run cannot be combined with --check")
        ctx.exit(2)
    if no_kiro and (kiro or kiro_root or kiro_agents or forget_kiro_agents):
        console.failure("--no-kiro cannot be combined with Kiro enrollment options")
        ctx.exit(2)
    settings = get_settings(ctx, BraidSettings)

    from braid.commands.compose.compose import CommandCompose
    from braid.domain.engine import ComposeRequest, Mode

    request = ComposeRequest(
        agents_root=agents_root or settings.agents_root,
        claude_root=claude_root or settings.claude_root,
        config_root=config_root or settings.config_root,
        sources=sources,
        policies=policies,
        mode=Mode.CHECK if check else Mode.DRY_RUN if dry_run else Mode.SYNC,
        project_claude=not no_claude,
        enable_kiro=kiro,
        kiro_root=kiro_root or settings.kiro_root,
        kiro_agents=kiro_agents,
        forget_kiro_agents=forget_kiro_agents,
        project_kiro=not no_kiro,
    )
    result = CommandCompose(request).execute()
    for line in (result.output or "").splitlines():
        console.console.out(line, highlight=False)
    if result.error:
        console.console.print(console.format_failure(escape(result.error)), soft_wrap=True)
    if result.metadata["exit_code"]:
        ctx.exit(result.metadata["exit_code"])
