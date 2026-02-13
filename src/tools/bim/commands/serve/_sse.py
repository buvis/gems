from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

_subscribers: set[asyncio.Queue[str]] = set()
_watcher_task: asyncio.Task[None] | None = None


async def start_watcher(directory: str) -> None:
    global _watcher_task
    _watcher_task = asyncio.create_task(_watch_loop(directory))


async def stop_watcher() -> None:
    global _watcher_task
    if _watcher_task is not None:
        _watcher_task.cancel()
        _watcher_task = None


async def _watch_loop(directory: str) -> None:
    try:
        from watchfiles import awatch
    except ImportError:
        return

    async for changes in awatch(directory):
        files = [str(path) for _change, path in changes]
        msg = json.dumps({"type": "file_change", "files": files})
        dead: list[asyncio.Queue[str]] = []
        for q in _subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _subscribers.discard(q)


async def _event_stream(queue: asyncio.Queue[str]) -> AsyncGenerator[str, None]:
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {msg}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        _subscribers.discard(queue)


@router.get("/events")
async def events() -> StreamingResponse:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=64)
    _subscribers.add(queue)
    return StreamingResponse(_event_stream(queue), media_type="text/event-stream")
