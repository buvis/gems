from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options
from buvis.pybase.result import FatalError

from sysup.settings import SysupSettings

if TYPE_CHECKING:
    from sysup.config import ExpiryItem, SysupCommand, SysupConfig
    from sysup.step_result import StepResult


def _is_tty() -> bool:
    return sys.stdin.isatty()


def _report_step(step: StepResult) -> None:
    if step.status == "expiring":
        console.warning(step.message or f"{step.label} expiring")
    elif step.success:
        console.success(step.message or f"{step.label} updated")
    else:
        console.failure(step.message or f"{step.label} failed")


def _parse_only(only: tuple[str, ...]) -> set[str]:
    names: set[str] = set()
    for item in only:
        names.update(part.strip() for part in item.split(",") if part.strip())
    return names


def _describe(name: str, command: SysupCommand) -> str:
    kind = f"use:{command.use}" if command.use is not None else "run"
    guards = []
    if command.when.os is not None:
        guards.append(f"os={command.when.os}")
    if command.when.check is not None:
        guards.append(f"check={command.when.check}")
    suffix = f" ({', '.join(guards)})" if guards else ""
    return f"{command.order:>4}  {name}  [{kind}]{suffix}"


def _filter_plan(
    cfg: SysupConfig, plan: list[tuple[str, SysupCommand]], only: tuple[str, ...], tags: tuple[str, ...]
) -> list[tuple[str, SysupCommand]]:
    """Apply name and tag filters, reporting unknown or inapplicable names."""
    only_names = _parse_only(only)
    if only_names:
        selected_names = {name for name, _ in plan}
        for requested in sorted(only_names):
            if requested not in cfg.commands:
                console.failure(f"unknown command '{requested}', skipping")
            elif requested not in selected_names:
                console.info(f"'{requested}' does not apply on this host, skipping")
        plan = [(name, command) for name, command in plan if name in only_names]

    if tags:
        wanted = set(tags)
        plan = [(name, command) for name, command in plan if wanted & set(command.tags)]
    return plan


def _entry_line(name: str, entry: dict[str, Any], qualifier: str = "") -> str:
    suffix = f", {qualifier}" if qualifier else ""
    hint = f"; run: sysup refresh {name}" if entry.get("kind") == "item" else ""
    return f"{name} ({entry['status']}{suffix}): {'; '.join(entry['details'])}{hint}"


def _print_summary(entries: dict[str, Any], checked: set[str]) -> None:
    from sysup.step_result import RED

    if not entries:
        return
    console.nl()
    console.warning(f"attention: {len(entries)} unresolved")
    for name, entry in sorted(entries.items()):
        qualifier = "" if name in checked else "not rechecked this run"
        line = _entry_line(name, entry, qualifier)
        if entry["status"] in RED:
            console.failure(line)
        else:
            console.warning(line)


def _notify(cfg: SysupConfig, entries: dict[str, Any]) -> dict[str, Any]:
    from sysup.attention import mark_notified, to_notify

    names = to_notify(entries)
    if not names:
        return entries
    url = cfg.ntfy.url or os.environ.get("NTFY_URL")
    topic = cfg.ntfy.topic or os.environ.get("NTFY_TOPIC")
    if not url or not topic:
        console.warning("notification not sent: ntfy not configured")
        return entries
    credentials = ""
    if cfg.ntfy.credentials_file:
        path = Path(cfg.ntfy.credentials_file).expanduser()
        try:
            credentials = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            console.warning(f"notification not sent: credentials file not readable: {path}")
            return entries

    from buvis.pybase.adapters.ntfy import send_ntfy

    title = f"sysup on {platform.node()}: {len(names)} need attention"
    message = "\n".join(f"{entries[name]['status']} {name}: {entries[name]['details'][0]}" for name in names)
    reason = send_ntfy(url, topic, title, message, credentials=credentials)
    if reason is not None:
        console.warning(f"notification not sent: {reason}")
        return entries
    return mark_notified(entries, names)


@click.group(invoke_without_command=True, help="Run applicable system and tooling updates")
@click.option("--only", multiple=True, help="Run only these command names (comma-separated or repeated).")
@click.option("--tag", "tags", multiple=True, help="Run only commands carrying one of these tags.")
@click.option("--list", "list_plan", is_flag=True, help="Print the resolved plan for this host and exit.")
@click.option("--dry-run", is_flag=True, help="Show what would run without running it.")
@buvis_options(settings_class=SysupSettings)
@click.pass_context
def cli(
    ctx: click.Context,
    only: tuple[str, ...],
    tags: tuple[str, ...],
    list_plan: bool,
    dry_run: bool,
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    from sysup.attention import exit_code, fold_results, read_state, write_state
    from sysup.config import applicable_commands, applicable_items, load_config
    from sysup.runner import Runner

    # Honour the same --config / --config-dir the buvis_options wrapper resolved
    # settings from, so the plan and SysupSettings come from ONE source (PRD 00084).
    obj = ctx.obj or {}
    try:
        cfg = load_config(config_dir=obj.get("config_dir"), config_path=obj.get("config_path"))
    except FatalError as exc:
        console.panic(str(exc))
        return

    plan = _filter_plan(cfg, applicable_commands(cfg), only, tags)

    if list_plan:
        if not plan:
            console.info("no applicable commands for this host")
        for name, command in plan:
            console.info(_describe(name, command))
        return

    results: list[StepResult] = []
    try:
        for step in Runner(cfg, dry_run=dry_run).run(plan):
            _report_step(step)
            results.append(step)
    except FatalError as exc:
        console.panic(str(exc))
        return
    if dry_run:
        return
    checked = {name for name, _ in plan} | {name for name, _ in applicable_items(cfg)}
    entries = fold_results(read_state(), checked, results, datetime.now(timezone.utc))
    _print_summary(entries, checked)
    entries = _notify(cfg, entries)
    try:
        write_state(entries)
    except OSError as exc:
        console.panic(f"could not write attention state: {exc}")
        return
    if exit_code(results):
        ctx.exit(1)


@cli.command(help="Show persisted attention without running updates")
@click.pass_context
def status(ctx: click.Context) -> None:
    from sysup.attention import read_state
    from sysup.step_result import RED

    entries = read_state()
    if not entries:
        console.success("nothing needs attention")
        return
    for name, entry in sorted(entries.items()):
        line = _entry_line(name, entry, f"checked {entry['last_checked']}")
        if entry["status"] in RED:
            console.failure(line)
        else:
            console.warning(line)
    if any(entry["status"] in RED for entry in entries.values()):
        ctx.exit(1)


@cli.command(name="refresh", help="Walk through renewing a tracked credential on this terminal")
@click.argument("item")
@click.pass_context
def refresh(ctx: click.Context, item: str) -> None:
    if not _is_tty():
        console.panic("sysup refresh needs a terminal")
        return

    import getpass

    from sysup.config import load_config
    from sysup.refresh import run_refresh

    obj = ctx.obj or {}
    try:
        cfg = load_config(config_dir=obj.get("config_dir"), config_path=obj.get("config_path"))
    except FatalError as exc:
        console.panic(str(exc))
        return

    expiry_item = cfg.expiry.get(item)
    if expiry_item is None:
        console.panic(f"unknown expiry item '{item}'")
        return
    if not expiry_item.enabled:
        console.panic(f"item '{item}' is disabled; enable it in buvis-sysup.local.yaml first")
        return
    if expiry_item.refresh is None:
        console.panic(f"item '{item}' has no refresh procedure")
        return

    console.print(expiry_item.refresh.instructions, mode="raw")
    console.info("press Enter when done")
    input()

    result = run_refresh(item, expiry_item.refresh, lambda: getpass.getpass("paste the new secret: "))
    _report_step(result)
    if not result.success:
        ctx.exit(1)
        return

    _recheck_item(ctx, cfg, item, expiry_item)


def _recheck_item(ctx: click.Context, cfg: SysupConfig, item: str, expiry_item: ExpiryItem) -> None:
    """Re-check one item after a successful refresh, fold, persist and exit.

    Only an ``ok`` recheck clears the entry; ``expiring``, ``expired`` and
    ``unknown`` update it. Exit follows :func:`exit_code`: ``ok`` / ``expiring``
    exit 0, ``expired`` / ``unknown`` exit 1.
    """
    from sysup.attention import exit_code, fold_results, read_state, write_state
    from sysup.runner import Runner

    recheck = list(Runner(cfg).check_items([(item, expiry_item)]))
    for step in recheck:
        _report_step(step)
    entries = fold_results(read_state(), {item}, recheck, datetime.now(timezone.utc))
    try:
        write_state(entries)
    except OSError as exc:
        console.panic(f"could not write attention state: {exc}")
        return
    if exit_code(recheck):
        ctx.exit(1)


if __name__ == "__main__":
    cli()
