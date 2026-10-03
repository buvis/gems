"""Shared fixtures and builders for the maintain test package."""

from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from buvis.pybase.filesystem import atomic_write_text
from klyreon.ingest.moc import MEMBERS_CLOSE, MEMBERS_OPEN
from klyreon.spec.model import Document, FileKind
from klyreon.spec.writer import serialize

pytestmark = pytest.mark.klyreon

TZ = dt.timezone(dt.timedelta(hours=2))
NOW = dt.datetime(2026, 4, 11, 14, 53, 0, tzinfo=TZ)


def write_zettel(
    root: Path,
    zid: str,
    *,
    title: str | None = None,
    concept_type: str = "thesis",
    assent: str = "tentative",
    lifecycle: str = "fleeting",
    processed: bool = False,
    sources: list[str] | None = None,
    links: list[dict[str, str]] | None = None,
    mocs: list[str] | None = None,
    doubts: list[dict[str, object]] | None = None,
    delivered_as: str | None = None,
    created: dt.datetime | None = None,
    updated: dt.datetime | None = None,
) -> str:
    """Write a spec-valid concept zettel; return its vault-relative path.

    ``created`` defaults to the datetime encoded by ``zid`` so the validator's
    id/created-agree-to-the-second rule always holds.
    """
    title = title or f"Zettel {zid}"
    if created is None:
        created = dt.datetime.strptime(zid, "%Y%m%d%H%M%S").replace(tzinfo=TZ)
    front: dict[str, object] = {
        "id": zid,
        "title": title,
        "created": created.isoformat(),
        "type": "note",
    }
    if updated is not None:
        front["updated"] = updated.isoformat()
    front["processed"] = processed
    front["concept-type"] = concept_type
    front["assent"] = assent
    front["lifecycle"] = lifecycle
    front["claims"] = [{"id": "c1", "statement": f"{title} asserts something."}]
    if doubts is not None:
        front["doubts"] = doubts
    if sources is not None:
        front["sources"] = sources
    if links is not None:
        front["links"] = links
    if mocs is not None:
        front["mocs"] = mocs
    if delivered_as is not None:
        front["delivered-as"] = delivered_as
    body = f"\n# {title}\n\n{title} body text.\n"
    rel = f"wiki/notes/{zid}.md"
    doc = Document(path=rel, kind=FileKind.ZETTEL, frontmatter=front, body=body, h1=title)
    atomic_write_text(root / rel, serialize(doc))
    return rel


def write_source(root: Path, rel: str, *, title: str = "A source", source_type: str = "article") -> str:
    """Write a minimal spec-valid source document; return its vault-relative path."""
    front: dict[str, object] = {
        "id": Path(rel).stem,
        "title": title,
        "created": NOW.isoformat(),
        "type": source_type,
    }
    body = f"\n# {title}\n\nSource body.\n"
    doc = Document(path=rel, kind=FileKind.SOURCE, frontmatter=front, body=body, h1=title)
    atomic_write_text(root / rel, serialize(doc))
    return rel


def write_moc(root: Path, slug: str, members: list[str], *, prose_above: str = "", prose_below: str = "") -> str:
    """Write a MOC with a member block flanked by optional prose."""
    links = "\n".join(f"- [{Path(m).stem}]({m})" for m in members)
    middle = f"\n{links}\n" if links else "\n"
    block = f"{MEMBERS_OPEN}{middle}{MEMBERS_CLOSE}"
    front: dict[str, object] = {
        "id": slug,
        "title": slug.replace("-", " ").title(),
        "created": "2026-01-01T09:00:00+02:00",
        "kind": "moc",
    }
    body = f"\n# {slug.replace('-', ' ').title()}\n\n{prose_above}{block}{prose_below}\n"
    rel = f"wiki/mocs/{slug}.md"
    doc = Document(path=rel, kind=FileKind.AUX, frontmatter=front, body=body, h1=slug.replace("-", " ").title())
    atomic_write_text(root / rel, serialize(doc))
    return rel


def make_vault(root: Path) -> Path:
    """Create an empty vault skeleton under ``root``."""
    for sub in ("sources", "sources/archive/2026-04", "wiki/notes", "wiki/mocs", "wiki/trails"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


# --------------------------------------------------------------------------- #
# git-operable temp vault (same proven pattern as the ingest tests)
# --------------------------------------------------------------------------- #


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)


def _git_operable(base: Path) -> bool:
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


def _git_base(tmp_path: Path) -> Path | None:
    for candidate in (tmp_path, Path("/tmp")):
        if _git_operable(candidate):
            return Path(tempfile.mkdtemp(prefix="klyreon-maintain-git-", dir=str(candidate)))
    return None


@pytest.fixture
def git_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """A git-initialised empty vault with one human seed commit, XDG isolated."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    base = _git_base(tmp_path)
    if base is None:
        pytest.skip("no git-operable temp directory available in this environment")
    root = base / "vault"
    make_vault(root)
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


def commit_all(root: Path, message: str = "seed vault") -> None:
    """Commit everything currently in the working tree under the human identity."""
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)
