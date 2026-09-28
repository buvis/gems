"""REST routes for ``postup serve``.

Two route groups behind one router:

* **Payload** (``GET``, unauthenticated reads on loopback) — the exact URLs the
  frontend prod loader fetches (``adapters/web/frontend/src/lib/payload.js``
  ``loadFromApi``): ``/api/data``, ``/api/epics``, ``/api/data-prev``,
  ``/api/history``. A never-collected ``out_dir`` returns the explicit
  empty-portfolio state (``repos: []``) at 200, never a 500 — the loader reads
  that as its empty state (design decision: serve last data until refreshed; no
  auto-collect on start).

* **Triggers** (``POST``, token-guarded) — ``/api/actions/collect`` and
  ``/api/actions/enrich`` run the *same* command classes as the CLI
  (``CommandCollect`` / ``CommandEnrich``) through the composition root
  (all-interface rule; no reimplementation here). A run holds a process-wide
  lock; a concurrent trigger while one is active is rejected with an
  "already running" status rather than starting a second run.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.result import CommandResult
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from postup.adapters.web._security import confine_path, require_token
from postup.domain.contracts import SCHEMA_VERSION

if TYPE_CHECKING:
    from postup.settings import PostupSettings

router = APIRouter()

# One run at a time across the process — the collect/enrich triggers are
# serialized so a second trigger arriving while a run is active is rejected
# rather than launched. A lock (not a bool) so the check-and-set is atomic
# under the event loop.
_run_lock = asyncio.Lock()

# The empty-portfolio payload served when ``out_dir`` has never been collected.
# Shaped like a valid ``PortfolioData`` with no repos, so the frontend loader's
# ``toState`` treats it as the (non-error) empty state, not needs-collect-error.
_EMPTY_PAYLOAD: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "generated_at": "",
    "since_days": 0,
    "repos": [],
    "skipped": [],
    "external": {"review_requested": [], "authored": [], "error": None},
}


def _out_dir(request: Request) -> Path:
    return Path(str(request.app.state.out_dir)).expanduser().resolve()


def _read_json_contract(request: Request, filename: str) -> Any | None:
    """Read one JSON contract from ``out_dir``, confined; None when absent.

    The filename is a fixed contract name, but it is still routed through
    :func:`confine_path` so the read can never escape ``out_dir`` (the
    confine-request-derived-paths invariant, defence in depth).
    """
    out_dir = _out_dir(request)
    resolved = confine_path(str(out_dir / filename), request.app.state)
    if not resolved.is_file():
        return None
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"unreadable {filename}: {exc}") from exc


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/data")
async def get_data(request: Request) -> JSONResponse:
    """Current payload (``data.json``). Never-collected -> explicit empty state."""
    data = _read_json_contract(request, "data.json")
    if data is None:
        return JSONResponse(content=_EMPTY_PAYLOAD)
    return JSONResponse(content=data)


@router.get("/epics")
async def get_epics(request: Request) -> JSONResponse:
    """Enrichment payload (``epics.json``); 404 when not enriched."""
    epics = _read_json_contract(request, "epics.json")
    if epics is None:
        raise HTTPException(status_code=404, detail="no epics.json — run enrich")
    return JSONResponse(content=epics)


@router.get("/data-prev")
async def get_data_prev(request: Request) -> JSONResponse:
    """Previous payload snapshot (``data-prev.json``); 404 on first run."""
    prev = _read_json_contract(request, "data-prev.json")
    if prev is None:
        raise HTTPException(status_code=404, detail="no data-prev.json — only one run so far")
    return JSONResponse(content=prev)


@router.get("/history")
async def get_history(request: Request) -> PlainTextResponse:
    """History log (``history.jsonl``) as raw text; empty body when absent.

    The loader parses this with ``parseHistory`` (newline-delimited JSON,
    torn-line tolerant), so the contract is the raw file body, not JSON.
    """
    out_dir = _out_dir(request)
    resolved = confine_path(str(out_dir / "history.jsonl"), request.app.state)
    if not resolved.is_file():
        return PlainTextResponse(content="")
    try:
        return PlainTextResponse(content=resolved.read_text(encoding="utf-8"))
    except OSError as exc:
        raise HTTPException(status_code=422, detail=f"unreadable history.jsonl: {exc}") from exc


def _envelope_response(result: CommandResult) -> JSONResponse:
    body = result.to_dict()
    return JSONResponse(content=body, status_code=200 if body["success"] else 422)


async def _run_command(build: Any) -> JSONResponse:
    """Run a command class (built by ``build``) under the single-run lock.

    A concurrent trigger while a run is active is rejected with an
    "already running" failure envelope (HTTP 409), not queued or run in
    parallel. The command's own ``execute`` runs off the event loop so the
    server stays responsive during a long collect.
    """
    if _run_lock.locked():
        return JSONResponse(
            content=CommandResult(success=False, error="a collect or enrich run is already running").to_dict(),
            status_code=409,
        )
    async with _run_lock:
        command = build()
        result = await asyncio.to_thread(command.execute)
    return _envelope_response(result)


@router.post("/actions/collect")
async def trigger_collect(request: Request, _: None = Depends(require_token)) -> JSONResponse:
    """Run ``postup collect`` via the same command class as the CLI."""
    settings: PostupSettings = request.app.state.settings

    def build() -> Any:
        from postup.commands.collect.collect import CommandCollect

        return CommandCollect(settings)

    return await _run_command(build)


@router.post("/actions/enrich")
async def trigger_enrich(request: Request, _: None = Depends(require_token)) -> JSONResponse:
    """Run ``postup enrich`` via the same command class as the CLI."""
    settings: PostupSettings = request.app.state.settings

    def build() -> Any:
        from postup.commands.enrich.enrich import CommandEnrich

        return CommandEnrich(settings)

    return await _run_command(build)
