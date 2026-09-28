"""Shared fixtures for the ``postup serve`` web-adapter tests.

Imports are local to the fixtures so this conftest stays importable even when
the ``postup-web`` extra (fastapi/uvicorn/watchfiles) is absent; each consuming
test module guards itself with its own ``pytest.importorskip``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

# A minimal-but-valid data.json contract (schema_version 1) used to round-trip
# the payload endpoints. Kept small on purpose — the endpoints serve the file
# body verbatim, so the exact shape only needs to be valid JSON.
SAMPLE_DATA = {
    "schema_version": 1,
    "generated_at": "2026-09-28T10:00:00+00:00",
    "since_days": 60,
    "repos": [{"path": "/repos/gems", "owner": "buvis", "name": "gems"}],
    "skipped": [],
    "external": {"review_requested": [], "authored": [], "error": None},
}
SAMPLE_PREV = {**SAMPLE_DATA, "generated_at": "2026-09-27T10:00:00+00:00"}
SAMPLE_EPICS = {"schema_version": 1, "narrative": "all green", "repos": [], "todos": []}
SAMPLE_HISTORY = '{"at": "2026-09-27T10:00:00+00:00", "skipped": 0, "repos": {}}\n'


def make_settings(out_dir: Path) -> object:
    """Build real ``PostupSettings`` pointed at ``out_dir``."""
    from postup.settings import PostupSettings

    return PostupSettings(out_dir=str(out_dir))


def write_contracts(out_dir: Path) -> None:
    """Write the full set of file contracts into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data.json").write_text(json.dumps(SAMPLE_DATA), encoding="utf-8")
    (out_dir / "data-prev.json").write_text(json.dumps(SAMPLE_PREV), encoding="utf-8")
    (out_dir / "epics.json").write_text(json.dumps(SAMPLE_EPICS), encoding="utf-8")
    (out_dir / "history.jsonl").write_text(SAMPLE_HISTORY, encoding="utf-8")


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    """An empty, existing ``out_dir``."""
    d = tmp_path / "out"
    d.mkdir()
    return d


@pytest.fixture
def client(out_dir: Path) -> Iterator[object]:
    """A ``TestClient`` for the postup serve app over an empty ``out_dir``.

    The SSE watcher is patched out so tests never touch the real filesystem
    watcher; SSE behaviour is covered by its own unit test against the
    emit seam.
    """
    from postup.adapters.web.app import create_app
    from starlette.testclient import TestClient

    with (
        patch("postup.adapters.web.app.start_watcher", new_callable=AsyncMock),
        patch("postup.adapters.web.app.stop_watcher", new_callable=AsyncMock),
    ):
        app = create_app(make_settings(out_dir), host="127.0.0.1")
        with TestClient(app, base_url="http://127.0.0.1") as test_client:
            yield test_client
