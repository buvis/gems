from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from buvis.pybase.zettel import MarkdownZettelFormatter, MarkdownZettelRepository

from bim.commands.shared.os_open import open_in_os

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


async def handle_patch(file_path: str, args: dict[str, Any], app_state: Any) -> dict[str, str]:
    fp = Path(file_path)
    repo = MarkdownZettelRepository()
    zettel = repo.find_by_location(str(fp))
    data = zettel.get_data()

    target = args.get("target", "metadata")
    field = args["field"]
    value = args["value"]

    if target == "section":
        from bim.commands.shared.sections import replace_section
        replace_section(data, field, value)
    elif target == "reference":
        data.reference[field] = value
    else:
        data.metadata[field] = value

    formatted = MarkdownZettelFormatter.format(data)
    fp.write_text(formatted, encoding="utf-8")
    return {"status": "ok"}


async def handle_sync_note(file_path: str, args: dict[str, Any], app_state: Any) -> dict[str, str]:
    from bim.commands.sync_note.sync_note import CommandSyncNote

    target_system = args.get("target_system", "jira")
    jira_config = args.get("jira_config", {})
    cmd = CommandSyncNote(
        path_note=Path(file_path),
        target_system=target_system,
        jira_adapter_config=jira_config,
    )
    cmd.execute()
    return {"status": "ok"}


async def handle_create_note(file_path: str, args: dict[str, Any], app_state: Any) -> dict[str, str]:
    from bim.commands.create_note.create_note import CommandCreateNote

    directory = Path(file_path).parent if file_path else Path(str(app_state.default_directory))
    cmd = CommandCreateNote(
        path_zettelkasten=directory,
        zettel_type=args.get("type"),
        title=args.get("title"),
        tags=args.get("tags"),
    )
    cmd.execute()
    return {"status": "ok"}


async def handle_archive(file_path: str, args: dict[str, Any], app_state: Any) -> dict[str, str]:
    from bim.commands.archive_note.archive_note import archive_single

    archive_dir = Path(str(app_state.archive_directory)).expanduser().resolve()
    archive_single(Path(file_path), archive_dir, quiet=True)
    return {"status": "ok"}


async def handle_open(file_path: str, args: dict[str, Any], app_state: Any) -> dict[str, str]:
    fp = Path(file_path)
    open_in_os(fp)
    return {"status": "ok"}


async def handle_format(file_path: str, args: dict[str, Any], app_state: Any) -> dict[str, str]:
    from bim.commands.format_note.format_note import format_single

    format_single(Path(file_path), in_place=True, quiet=True)
    return {"status": "ok"}


async def handle_delete(file_path: str, args: dict[str, Any], app_state: Any) -> dict[str, str]:
    from bim.commands.delete_note.delete_note import delete_single

    delete_single(Path(file_path), quiet=True)
    return {"status": "ok"}


async def handle_import(file_path: str, args: dict[str, Any], app_state: Any) -> dict[str, str]:
    from bim.commands.import_note.import_note import import_single

    zettelkasten = Path(str(app_state.default_directory)).expanduser().resolve()
    tags = args.get("tags")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    import_single(
        Path(file_path),
        zettelkasten,
        tags=tag_list,
        force_overwrite=args.get("force", False),
        remove_original=args.get("remove_original", False),
        quiet=True,
    )
    return {"status": "ok"}


ACTION_HANDLERS: dict[str, Any] = {
    "patch": handle_patch,
    "sync_note": handle_sync_note,
    "create_note": handle_create_note,
    "archive": handle_archive,
    "open": handle_open,
    "delete": handle_delete,
    "format": handle_format,
    "import": handle_import,
}
