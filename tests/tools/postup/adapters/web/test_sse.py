"""SSE watcher tests for ``postup serve``.

The load-bearing property (PRD 00067 Phase 1): an atomic-replace write
(00063: write temp -> ``os.replace``) must surface to the browser as exactly
one refresh event, not a storm. watchfiles coalesces the raw events of one
atomic replace into a single ``changes`` batch, and ``emit_for_batch`` turns
one batch into one broadcast — this test drives that seam deterministically
without depending on real filesystem timing.
"""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("fastapi")

from postup.adapters.web import _sse


@pytest.fixture(autouse=True)
def _clean_subscribers():
    _sse._subscribers.clear()
    yield
    _sse._subscribers.clear()


def _subscribe() -> asyncio.Queue[str]:
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=64)
    _sse._subscribers.add(q)
    return q


class TestEmitForBatch:
    def test_atomic_replace_batch_emits_exactly_one_event(self) -> None:
        q = _subscribe()
        # The event burst watchfiles delivers for one atomic replace of
        # data.json: a temp file created, then renamed onto data.json.
        atomic_replace_batch = [
            (1, "/out/.data.json.tmp123"),  # Change.added
            (3, "/out/.data.json.tmp123"),  # Change.deleted (the rename source)
            (2, "/out/data.json"),  # Change.modified (the rename target)
        ]

        _sse.emit_for_batch(atomic_replace_batch)

        assert q.qsize() == 1
        payload = json.loads(q.get_nowait())
        assert payload["type"] == "file_change"
        assert "/out/data.json" in payload["files"]

    def test_each_batch_is_one_event(self) -> None:
        q = _subscribe()
        _sse.emit_for_batch([(2, "/out/data.json")])
        _sse.emit_for_batch([(2, "/out/epics.json")])
        assert q.qsize() == 2

    def test_full_queue_subscriber_is_dropped(self) -> None:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        q.put_nowait("stale")
        _sse._subscribers.add(q)
        _sse.emit_for_batch([(2, "/out/data.json")])
        assert q not in _sse._subscribers


class TestWatcherLifecycle:
    def test_start_then_stop_clears_task(self) -> None:
        async def _run() -> None:
            await _sse.start_watcher("/nonexistent-dir-for-test")
            assert _sse._watcher_task is not None
            await _sse.stop_watcher()
            assert _sse._watcher_task is None

        asyncio.run(_run())
