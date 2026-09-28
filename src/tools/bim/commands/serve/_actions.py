from __future__ import annotations

import re
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from buvis.pybase.result import CommandResult
from fastapi import HTTPException

from bim.commands.serve._security import AppState, confine_path
from bim.commands.shared.os_open import open_in_os
from bim.dependencies import get_repo


def _resolve_templates(args: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Replace {field} placeholders in args values using row data."""
    resolved: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, str):
            resolved[k] = re.sub(
                r"\{(\w+)\}",
                lambda m: str(row.get(m.group(1), m.group(0))),
                v,
            )
        else:
            resolved[k] = v
    return resolved


async def handle_patch(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, Any]:
    fp = confine_path(file_path, app_state)
    from bim.commands.edit_note.edit_note import CommandEditNote
    from bim.params.edit_note import EditNoteParams

    target = args.get("target", "metadata")
    changes = {args["field"]: args["value"]}
    params = EditNoteParams(paths=[fp], changes=changes, target=target)
    result = CommandEditNote(params=params, repo=get_repo()).execute()
    return result.to_dict()


async def handle_sync_note(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, Any]:
    fp = confine_path(file_path, app_state)
    from bim.commands.sync_note.sync_note import CommandSyncNote
    from bim.dependencies import get_formatter, get_repo
    from bim.params.sync_note import SyncNoteParams

    target_system = args.get("target_system", "jira")
    jira_config = args.get("jira_config", {})
    params = SyncNoteParams(paths=[fp], target_system=target_system)
    cmd = CommandSyncNote(
        params=params,
        jira_adapter_config=jira_config,
        repo=get_repo(),
        formatter=get_formatter(),
    )
    result = cmd.execute()
    return result.to_dict()


async def handle_create_note(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, Any]:
    from bim.commands.create_note.create_note import CommandCreateNote
    from bim.dependencies import get_hook_runner, get_repo, get_templates
    from bim.params.create_note import CreateNoteParams

    directory = confine_path(file_path, app_state).parent if file_path else Path(str(app_state.default_directory))
    params = CreateNoteParams(
        zettel_type=args.get("type"),
        title=args.get("title"),
        tags=args.get("tags"),
        extra_answers=args.get("extra_answers"),
    )
    cmd = CommandCreateNote(
        params=params,
        path_zettelkasten=directory,
        repo=get_repo(),
        templates=get_templates(),
        hook_runner=get_hook_runner(),
    )
    result = cmd.execute()
    return result.to_dict()


async def handle_archive(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, Any]:
    fp = confine_path(file_path, app_state)
    from bim.commands.archive_note.archive_note import CommandArchiveNote
    from bim.params.archive_note import ArchiveNoteParams

    archive_dir = Path(str(app_state.archive_directory)).expanduser().resolve()
    zettelkasten_dir = Path(str(app_state.default_directory)).expanduser().resolve()
    params = ArchiveNoteParams(paths=[fp])
    cmd = CommandArchiveNote(
        params=params,
        path_archive=archive_dir,
        path_zettelkasten=zettelkasten_dir,
        repo=get_repo(),
    )
    result = cmd.execute()
    return result.to_dict()


async def handle_open(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, Any]:
    fp = confine_path(file_path, app_state)
    open_in_os(fp)
    return CommandResult(success=True).to_dict()


async def handle_format(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, Any]:
    from bim.commands.format_note.format_note import CommandFormatNote
    from bim.dependencies import get_formatter, get_repo
    from bim.params.format_note import FormatNoteParams

    target = confine_path(file_path, app_state)
    params = FormatNoteParams(paths=[target], path_output=target)
    cmd = CommandFormatNote(
        params=params,
        repo=get_repo(),
        formatter=get_formatter(),
    )
    result = cmd.execute()
    return result.to_dict()


async def handle_delete(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, Any]:
    fp = confine_path(file_path, app_state)
    from bim.commands.delete_note.delete_note import CommandDeleteNote
    from bim.params.delete_note import DeleteNoteParams

    params = DeleteNoteParams(paths=[fp])
    cmd = CommandDeleteNote(params=params, repo=get_repo())
    result = cmd.execute()
    return result.to_dict()


async def handle_import(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, Any]:
    fp = confine_path(file_path, app_state)
    from bim.commands.import_note.import_note import CommandImportNote
    from bim.dependencies import get_formatter, get_repo
    from bim.params.import_note import ImportNoteParams

    zettelkasten = Path(str(app_state.default_directory)).expanduser().resolve()
    tags = args.get("tags")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    params = ImportNoteParams(
        paths=[fp],
        tags=tag_list,
        force=args.get("force", False),
        remove_original=args.get("remove_original", False),
    )
    cmd = CommandImportNote(
        params=params,
        path_zettelkasten=zettelkasten,
        repo=get_repo(),
        formatter=get_formatter(),
    )
    result = cmd.execute()
    return result.to_dict()


async def handle_triage_list(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, Any]:
    """List pending triage proposals. ``file_path`` is unused (lists the dir)."""
    if app_state.doc_settings is None:
        return CommandResult(success=False, error="[doc] section not configured; triage is unavailable").to_dict()
    from bim.commands.doc.triage.triage import CommandTriageList
    from bim.dependencies import get_triage_list_services
    from bim.params.doc_triage import TriageListParams

    cmd = CommandTriageList(
        services=get_triage_list_services(app_state.doc_settings),
        params=TriageListParams(),
    )
    return cmd.execute().to_dict()


async def handle_triage_approve(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, Any]:
    """Approve+promote a triage proposal named by ``file_path``.

    Two-stage confinement: ``confine_path`` first enforces the broad
    vault/archive/triage allow-list, then this handler narrows it to require
    the resolved path lie under ``<business_root>/_triage/`` specifically —
    otherwise a ``.proposed.yml`` placed anywhere in the vault or archive
    would be accepted. A path outside ``_triage/`` (or an unconfigured triage
    root) is refused with HTTP 403.
    """
    if app_state.doc_settings is None:
        return CommandResult(success=False, error="[doc] section not configured; triage is unavailable").to_dict()
    fp = confine_path(file_path, app_state)
    if not app_state.business_triage_root:
        raise HTTPException(status_code=403, detail="triage root is not configured")
    triage_root = Path(app_state.business_triage_root).expanduser().resolve()
    if not fp.is_relative_to(triage_root):
        raise HTTPException(status_code=403, detail="path is outside the triage directory")
    from bim.commands.doc.triage.triage import CommandTriageApprove
    from bim.dependencies import get_repo, get_triage_approve_services
    from bim.params.doc_triage import TriageApproveParams

    cmd = CommandTriageApprove(
        services=get_triage_approve_services(app_state.doc_settings, get_repo()),
        params=TriageApproveParams(proposed_yml_path=fp),
    )
    return cmd.execute().to_dict()


ActionHandler = Callable[[str, dict[str, Any], AppState], Coroutine[Any, Any, dict[str, Any]]]

ACTION_HANDLERS: dict[str, ActionHandler] = {
    "patch": handle_patch,
    "sync_note": handle_sync_note,
    "create_note": handle_create_note,
    "archive": handle_archive,
    "open": handle_open,
    "delete": handle_delete,
    "format": handle_format,
    "import": handle_import,
    "triage_list": handle_triage_list,
    "triage_approve": handle_triage_approve,
}
