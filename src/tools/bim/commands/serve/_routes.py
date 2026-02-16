from __future__ import annotations

import dataclasses
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from buvis.pybase.zettel.application.use_cases.query_zettels_use_case import QueryZettelsUseCase
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase
from buvis.pybase.zettel.domain.value_objects.property_schema import BUILTIN_SCHEMA

from bim.commands.serve._actions import ACTION_HANDLERS, _resolve_templates
from bim.commands.shared.os_open import open_in_os
from bim.dependencies import (
    get_evaluator,
    get_formatter,
    get_repo,
    list_query_files,
    parse_query_file,
    parse_query_spec,
    resolve_query_file,
)

router = APIRouter()

BUNDLED_QUERY_DIR = Path(__file__).parents[1] / "query"


def _get_directory(request: Request) -> str:
    return str(request.app.state.default_directory)


def _run_query(spec: Any, directory: str) -> dict[str, Any]:
    if spec.source.directory is None:
        spec.source.directory = directory
    repo = get_repo(extensions=spec.source.extensions)
    use_case = QueryZettelsUseCase(repo, get_evaluator())
    rows = use_case.execute(spec)
    columns = [dataclasses.asdict(c) for c in spec.columns] if spec.columns else []
    dashboard = dataclasses.asdict(spec.dashboard) if spec.dashboard else None

    # Merge builtin + manifest schema
    resolved_schema = {k: dataclasses.asdict(v) for k, v in BUILTIN_SCHEMA.items()}
    resolved_schema.update({k: dataclasses.asdict(v) for k, v in spec.schema.items()})

    item = dataclasses.asdict(spec.item) if spec.item else None
    actions = [dataclasses.asdict(a) for a in spec.actions] if spec.actions else []

    return {
        "rows": [_serialize_row(r) for r in rows],
        "columns": columns,
        "dashboard": dashboard,
        "count": len(rows),
        "schema": resolved_schema,
        "item": item,
        "actions": actions,
        "output": dataclasses.asdict(spec.output),
    }


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif hasattr(v, "plain"):
            out[k] = v.plain
        else:
            out[k] = v
    return out


def _serialize_dict(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif hasattr(v, "plain"):
            out[k] = v.plain
        else:
            out[k] = v
    return out


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/queries")
async def list_queries(request: Request) -> dict[str, Any]:
    found = list_query_files(bundled_dir=BUNDLED_QUERY_DIR)
    return {"queries": {name: str(path) for name, path in found.items()}}


@router.get("/queries/{name}")
async def get_query(name: str) -> dict[str, Any]:
    try:
        path = resolve_query_file(name, bundled_dir=BUNDLED_QUERY_DIR)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    spec = parse_query_file(str(path))
    return dataclasses.asdict(spec)


class AdhocQueryBody(BaseModel):
    spec: dict[str, Any]


@router.post("/queries/{name}/exec")
async def exec_query(name: str, request: Request) -> dict[str, Any]:
    directory = _get_directory(request)
    try:
        path = resolve_query_file(name, bundled_dir=BUNDLED_QUERY_DIR)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    spec = parse_query_file(str(path))
    return _run_query(spec, directory)


@router.post("/queries/_adhoc")
async def exec_adhoc(body: AdhocQueryBody, request: Request) -> dict[str, Any]:
    directory = _get_directory(request)
    spec = parse_query_spec(body.spec)
    return _run_query(spec, directory)


class PatchBody(BaseModel):
    field: str
    value: Any
    target: str = "metadata"  # metadata | reference | section


@router.patch("/zettels/{file_path:path}")
async def patch_zettel(file_path: str, body: PatchBody) -> dict[str, str]:
    fp = Path(file_path)
    if not fp.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    repo = get_repo()
    zettel = repo.find_by_location(str(fp))
    data = zettel.get_data()

    if body.target == "section":
        from bim.commands.shared.sections import replace_section
        replace_section(data, body.field, body.value)
    elif body.target == "reference":
        data.reference[body.field] = body.value
    else:
        data.metadata[body.field] = body.value

    formatted = PrintZettelUseCase(get_formatter()).execute(data)
    fp.write_text(formatted, encoding="utf-8")
    return {"status": "ok"}


@router.get("/zettels/{file_path:path}")
async def get_zettel(file_path: str) -> dict[str, Any]:
    fp = Path(file_path)
    if not fp.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    repo = get_repo()
    zettel = repo.find_by_location(str(fp))
    data = zettel.get_data()
    return {
        "metadata": _serialize_dict(data.metadata),
        "reference": _serialize_dict(data.reference),
        "sections": [{"heading": h, "body": b} for h, b in data.sections],
        "file_path": data.file_path,
    }


class OpenBody(BaseModel):
    path: str


@router.post("/open")
async def open_file(body: OpenBody) -> dict[str, str]:
    fp = Path(body.path)
    if not fp.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {body.path}")

    open_in_os(fp)

    return {"status": "ok"}


class ActionBody(BaseModel):
    file_path: str
    args: dict[str, Any] = {}
    row: dict[str, Any] = {}


@router.post("/actions/{action_name}")
async def exec_action(action_name: str, body: ActionBody, request: Request) -> dict[str, str]:
    handler = ACTION_HANDLERS.get(action_name)
    if not handler:
        raise HTTPException(status_code=404, detail=f"Unknown action: {action_name}")
    resolved_args = _resolve_templates(body.args, body.row)
    return await handler(body.file_path, resolved_args, request.app.state)
