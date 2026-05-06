"""Shared fixtures for ``tests/tools/bim/doc/``.

The cycle-3 doubt-fix added a Pydantic validator on ``DocPaths.business_root``
requiring it to live under ``Path.home()`` (so the synthetic ``~<absolute>``
fallback in ``to_tilde_path`` cannot reach zettel frontmatter in production).
Tests in this directory pass ``tmp_path / "Business"`` as ``business_root``,
which on macOS resolves to ``/private/var/folders/...`` — outside ``~``.

This conftest auto-redirects ``Path.home()`` to ``tmp_path`` for every test
that takes the ``tmp_path`` fixture, so existing tests keep working without
each one having to opt into the patch. Tests that don't use ``tmp_path`` are
unaffected.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _home_under_tmp(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Point ``Path.home()`` (and ``$HOME``) at ``tmp_path`` for the test.

    Skipped when the test does not request ``tmp_path``; settings tests that
    exercise the validator with explicit non-home paths can therefore still
    fail loudly.
    """
    if "tmp_path" not in request.fixturenames:
        return
    tmp_path: Path = request.getfixturevalue("tmp_path")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
