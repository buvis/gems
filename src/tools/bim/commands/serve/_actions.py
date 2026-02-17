from __future__ import annotations

import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from buvis.pybase.zettel.application.use_cases.update_zettel_use_case import UpdateZettelUseCase

from bim.commands.shared.os_open import open_in_os
from bim.dependencies import get_repo


@dataclass
class AppState:
    default_directory: str
    archive_directory: str | None


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


async def handle_patch(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, str]:
    fp = Path(file_path)
    repo = get_repo()
    zettel = repo.find_by_location(str(fp))

    target = args.get("target", "metadata")
    changes = {args["field"]: args["value"]}
    UpdateZettelUseCase(repo).execute(zettel, changes, target)
    return {"status": "ok"}


async def handle_sync_note(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, str]:
    from bim.commands.sync_note.sync_note import CommandSyncNote
    from bim.dependencies import get_formatter, get_repo
    from bim.params.sync_note import SyncNoteParams

    target_system = args.get("target_system", "jira")
    jira_config = args.get("jira_config", {})
    params = SyncNoteParams(paths=[Path(file_path)], target_system=target_system)
    cmd = CommandSyncNote(
        params=params,
        jira_adapter_config=jira_config,
        repo=get_repo(),
        formatter=get_formatter(),
    )
    result = cmd.execute()
    if not result.success:
        return {"status": "error", "message": result.error or "Sync failed"}
    return {"status": "ok"}


async def handle_create_note(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, str]:
    from bim.commands.create_note.create_note import CommandCreateNote
    from bim.dependencies import get_hook_runner, get_repo, get_templates
    from bim.params.create_note import CreateNoteParams

    directory = Path(file_path).parent if file_path else Path(str(app_state.default_directory))
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
    if not result.success:
        return {"status": "error", "message": result.error or "Create failed"}
    return {"status": "ok"}


async def handle_archive(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, str]:
    from bim.commands.archive_note.archive_note import CommandArchiveNote
    from bim.params.archive_note import ArchiveNoteParams

    archive_dir = Path(str(app_state.archive_directory)).expanduser().resolve()
    zettelkasten_dir = Path(str(app_state.default_directory)).expanduser().resolve()
    params = ArchiveNoteParams(paths=[Path(file_path)])
    cmd = CommandArchiveNote(
        params=params,
        path_archive=archive_dir,
        path_zettelkasten=zettelkasten_dir,
        repo=get_repo(),
    )
    result = cmd.execute()
    if not result.success:
        return {"status": "error", "message": result.error or "Archive failed"}
    return {"status": "ok"}


async def handle_open(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, str]:
    fp = Path(file_path)
    open_in_os(fp)
    return {"status": "ok"}


async def handle_format(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, str]:
    from bim.commands.format_note.format_note import CommandFormatNote
    from bim.dependencies import get_formatter, get_repo
    from bim.params.format_note import FormatNoteParams

    target = Path(file_path)
    params = FormatNoteParams(paths=[target], path_output=target)
    cmd = CommandFormatNote(
        params=params,
        repo=get_repo(),
        formatter=get_formatter(),
    )
    result = cmd.execute()
    if not result.success:
        return {"status": "error", "message": result.error or "Formatting failed"}
    return {"status": "ok"}


async def handle_delete(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, str]:
    from bim.commands.delete_note.delete_note import CommandDeleteNote
    from bim.params.delete_note import DeleteNoteParams

    params = DeleteNoteParams(paths=[Path(file_path)])
    cmd = CommandDeleteNote(params=params, repo=get_repo())
    result = cmd.execute()
    if not result.success:
        return {"status": "error", "message": result.error or "Delete failed"}
    return {"status": "ok"}


async def handle_import(file_path: str, args: dict[str, Any], app_state: AppState) -> dict[str, str]:
    from bim.commands.import_note.import_note import CommandImportNote
    from bim.dependencies import get_formatter, get_repo
    from bim.params.import_note import ImportNoteParams

    zettelkasten = Path(str(app_state.default_directory)).expanduser().resolve()
    tags = args.get("tags")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    params = ImportNoteParams(
        paths=[Path(file_path)],
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
    if not result.success:
        return {"status": "error", "message": result.error or "Import failed"}
    return {"status": "ok"}


ActionHandler = Callable[[str, dict[str, Any], AppState], Coroutine[Any, Any, dict[str, str]]]

ACTION_HANDLERS: dict[str, ActionHandler] = {
    "patch": handle_patch,
    "sync_note": handle_sync_note,
    "create_note": handle_create_note,
    "archive": handle_archive,
    "open": handle_open,
    "delete": handle_delete,
    "format": handle_format,
    "import": handle_import,
}
