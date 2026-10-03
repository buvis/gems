"""Shared fixtures for the ingest test package."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
from collections.abc import Generator
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


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)


def _git_operable(base: Path) -> bool:
    """Return True when 'git init' succeeds under ``base`` (some sandboxes deny it)."""
    probe = base / "git-probe"
    try:
        probe.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            ["git", "-C", str(probe), "init", "-q"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    finally:
        shutil.rmtree(probe, ignore_errors=True)
    return completed.returncode == 0


@pytest.fixture
def git_vault(tmp_path: Path) -> Generator[Path, None, None]:
    """A git-initialised empty vault skeleton with one seed commit.

    pytest's tmp_path can live under a sandbox-restricted root where ``git init``
    is denied (exit 128); prefer it (CI), fall back to ``/tmp``, else skip -- the
    same pattern 00074's git tests use.
    """
    base: Path | None = None
    for candidate in (tmp_path, Path("/tmp")):
        if _git_operable(candidate):
            base = Path(tempfile.mkdtemp(prefix="klyreon-ingest-git-", dir=str(candidate)))
            break
    if base is None:
        pytest.skip("no git-operable temp directory available in this environment")

    root = base / "vault"
    for sub in ("sources/2026-05", "wiki/notes", "wiki/mocs", "wiki/trails"):
        (root / sub).mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Human Owner")
    _git(root, "config", "user.email", "human@example.com")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-q", "-m", "seed")
    try:
        yield root
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _git_base(tmp_path: Path) -> Path | None:
    for candidate in (tmp_path, Path("/tmp")):
        if _git_operable(candidate):
            return Path(tempfile.mkdtemp(prefix="klyreon-ingest-git-", dir=str(candidate)))
    return None


def _init_git(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Human Owner")
    _git(root, "config", "user.email", "human@example.com")
    _git(root, "config", "commit.gpgsign", "false")


@pytest.fixture
def git_happy_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """A git vault seeded with the four happy-path sources + an architecture MOC."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    base = _git_base(tmp_path)
    if base is None:
        pytest.skip("no git-operable temp directory available in this environment")
    root = base / "vault"
    for sub in ("sources", "wiki/notes", "wiki/mocs", "wiki/trails"):
        (root / sub).mkdir(parents=True)
    shutil.copytree(HAPPY_SOURCES, root / "sources", dirs_exist_ok=True)
    shutil.copy(INGEST_FIXTURES / "architecture-moc.md", root / "wiki" / "mocs" / "architecture.md")
    _init_git(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed vault")
    try:
        yield root
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def git_conflict_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """A git vault = the conflict baseline (accepted + rejected zettels, epistemics MOC)."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    base = _git_base(tmp_path)
    if base is None:
        pytest.skip("no git-operable temp directory available in this environment")
    root = base / "vault"
    shutil.copytree(CONFLICT_VAULT, root)
    for sub in ("sources/2026-05", "wiki/notes", "wiki/trails"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    _init_git(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed conflict vault")
    try:
        yield root
    finally:
        shutil.rmtree(base, ignore_errors=True)
