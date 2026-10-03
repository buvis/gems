"""Shared fixtures for the ingest test package."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.klyreon

INGEST_FIXTURES = Path(__file__).parents[1] / "fixtures" / "ingest"
HAPPY_SOURCES = INGEST_FIXTURES / "sources"
CONFLICT_VAULT = INGEST_FIXTURES / "conflict-vault"
CONFLICT_SOURCES = INGEST_FIXTURES / "conflict-sources"


def load_payloads() -> ModuleType:
    """Load the fixture payloads module by path (the tests tree is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "klyreon_ingest_fixture_payloads",
        INGEST_FIXTURES / "payloads.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def payloads() -> ModuleType:
    return load_payloads()


@pytest.fixture
def ingest_fixtures() -> Path:
    return INGEST_FIXTURES


@pytest.fixture
def happy_vault(tmp_path: Path) -> Path:
    """A vault skeleton seeded with the four happy-path sources + an architecture MOC."""
    root = tmp_path / "vault"
    for sub in ("sources", "wiki/notes", "wiki/mocs", "wiki/trails"):
        (root / sub).mkdir(parents=True)
    shutil.copytree(HAPPY_SOURCES, root / "sources", dirs_exist_ok=True)
    shutil.copy(
        INGEST_FIXTURES / "architecture-moc.md",
        root / "wiki" / "mocs" / "architecture.md",
    )
    return root


@pytest.fixture
def conflict_vault(tmp_path: Path) -> Path:
    """A writable copy of the accepted/rejected-claim baseline vault."""
    root = tmp_path / "cvault"
    shutil.copytree(CONFLICT_VAULT, root)
    for sub in ("sources", "wiki/notes", "wiki/trails"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root
