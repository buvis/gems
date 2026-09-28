"""Server-sent events for ``postup serve``.

Mirrors the ``bim serve`` ``_sse.py`` watcher: a single ``watchfiles.awatch``
loop over ``out_dir`` fans a ``file_change`` message out to every subscribed
browser queue. The frontend re-fetches the payload on that event.

The one addition over bim is debounce. The collect/enrich write path (PRD
00063) publishes each contract with an atomic ``tempfile + os.replace``, which
``watchfiles`` surfaces as a burst of raw change events for one logical
refresh. ``watchfiles.awatch`` already coalesces raw events arriving inside its
``step`` window into a single ``changes`` batch; :func:`emit_for_batch` then
turns each batch into exactly one broadcast, so one atomic replace yields one
browser re-fetch rather than a storm.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Iterable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

# watchfiles' own event-batching window (milliseconds). Raw filesystem events
# arriving inside it are folded into one ``changes`` set, so an atomic replace
# (write temp -> os.replace) surfaces as a single batch rather than a storm.
_DEBOUNCE_MS = 300

_subscribers: set[asyncio.Queue[str]] = set()
_watcher_task: asyncio.Task[None] | None = None


async def start_watcher(directory: str) -> None:
    """Start the background ``out_dir`` watcher task."""
    global _watcher_task
    _watcher_task = asyncio.create_task(_watch_loop(directory))


async def stop_watcher() -> None:
    """Cancel the background watcher task, if running."""
    global _watcher_task
    if _watcher_task is not None:
        _watcher_task.cancel()
        _watcher_task = None


def _message_for_batch(changes: Iterable[tuple[Any, Any]]) -> str:
    """Fold one watchfiles ``changes`` batch into a single SSE message body."""
    files = sorted({str(path) for _change, path in changes})
    return json.dumps({"type": "file_change", "files": files})


def emit_for_batch(changes: Iterable[tuple[Any, Any]]) -> str:
    """Broadcast exactly one ``file_change`` event for one ``changes`` batch.

    A watchfiles batch already coalesces the burst of raw events an atomic
    replace produces, so one batch maps to one broadcast. Returns the emitted
    message body (for tests and callers that want to assert on it).
    """
    msg = _message_for_batch(changes)
    _broadcast(msg)
    return msg


async def _watch_loop(directory: str) -> None:
    try:
        from watchfiles import awatch
    except ImportError:
        return

    async for changes in awatch(directory, step=_DEBOUNCE_MS):
        emit_for_batch(changes)


def _broadcast(msg: str) -> None:
    dead: list[asyncio.Queue[str]] = []
    for queue in _subscribers:
        try:
            queue.put_nowait(msg)
        except asyncio.QueueFull:
            dead.append(queue)
    for queue in dead:
        _subscribers.discard(queue)


async def _event_stream(queue: asyncio.Queue[str]) -> AsyncGenerator[str, None]:
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {msg}\n\n"
            except TimeoutError:
                yield ": keepalive\n\n"
    finally:
        _subscribers.discard(queue)


@router.get("/events")
async def events(request: Request) -> StreamingResponse:  # noqa: ARG001  # FastAPI needs request in scope
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=64)
    _subscribers.add(queue)
    return StreamingResponse(_event_stream(queue), media_type="text/event-stream")
