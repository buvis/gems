from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

MINIMAL_ZETTEL = """\
---
title: Original Title
type: note
tags:
  - alpha
  - beta
processed: false
publish: false
---

## Content

Some body text.
"""


@pytest.fixture
def minimal_zettel() -> str:
    return MINIMAL_ZETTEL


@pytest.fixture
def client(tmp_path: Path):
    """A ``TestClient`` for the bim serve app, shared across the ``test_serve_*``
    modules. Imports are local to the fixture so this conftest stays importable
    even when ``fastapi``/``httpx`` (the ``bim-web`` extra) are not installed;
    each consuming test module guards itself with its own
    ``pytest.importorskip`` calls."""
    from bim.commands.serve._app import create_app
    from starlette.testclient import TestClient

    zettels_dir = tmp_path / "zettels"
    zettels_dir.mkdir()
    with (
        patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
        patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
    ):
        app = create_app(default_directory=str(zettels_dir), archive_directory="archive")
        with TestClient(app, base_url="http://127.0.0.1") as test_client:
            yield test_client
