"""Shared fixtures for ``tests/tools/bim/doc/``.

A Pydantic validator on ``DocPaths.business_root`` requires it to live
under ``Path.home()`` (the iCloud-synced vault and business folders are
expected to be under ``~/Library/...``). Tests in this directory pass
``tmp_path / "Business"`` as ``business_root``, which on macOS resolves
to ``/private/var/folders/...`` — outside ``~``.

This conftest auto-redirects ``Path.home()`` to ``tmp_path`` for every
test that takes the ``tmp_path`` fixture, so existing tests keep working
without each one having to opt into the patch. Tests that don't use
``tmp_path`` are unaffected.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bim.commands.doc.shared.settings_models import (
    ClassifierSettings,
    DocPaths,
    DocSettings,
    OCRSettings,
    ZettelSettings,
)
from bim.commands.doc.shared.state_db import StateDB

FIXTURES = Path(__file__).parent / "fixtures"


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


def _make_settings(tmp_path: Path) -> DocSettings:
    paths = DocPaths.model_validate(
        {
            "business_root": str(tmp_path / "Business"),
            "vault_root": str(tmp_path / "Vault"),
            "vault_documents_subdir": "Zettelkasten/documents",
            "state_dir": str(tmp_path / "state"),
        }
    )
    return DocSettings(
        paths=paths,
        ocr=OCRSettings(),
        classifier=ClassifierSettings(),
        zettel=ZettelSettings(),
    )


@pytest.fixture
def settings(tmp_path: Path) -> DocSettings:
    """Shared ``DocSettings`` fixture for ``test_promote.py`` and
    ``test_promote_collision.py`` (lifted here so both files can use it
    without duplicating the helper)."""
    s = _make_settings(tmp_path)
    s.paths.business_root.mkdir(parents=True, exist_ok=True)
    return s


@pytest.fixture
def registry_path(tmp_path: Path) -> Path:
    src = FIXTURES / "issuers" / "with_aliases.yml"
    dst = tmp_path / "issuers.yml"
    dst.write_bytes(src.read_bytes())
    return dst


@pytest.fixture
def lock_path(tmp_path: Path) -> Path:
    return tmp_path / "issuers.lock"


@pytest.fixture
def state_db(tmp_path: Path) -> StateDB:
    return StateDB.open(tmp_path / "state" / "state.db")
