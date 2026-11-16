"""Shared fixtures for the ``bim tx`` tests: a scratch vault and note builders.

Every test here runs against a vault under ``tmp_path``, with the ``BUVIS_BIM_*``
environment, ``HOME``, ``XDG_STATE_HOME`` and ``BUVIS_CONFIG_DIR`` isolated, so
neither the developer's config nor the private vault can leak in.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class TxVault:
    root: Path
    zettelkasten: Path
    folder: Path
    state_home: Path
    home: Path
    config_dir: Path


@pytest.fixture(autouse=True)
def tx_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TxVault:
    """Create ``tmp_path/vault/notes/tiromex`` and point bim at it."""
    for name in list(os.environ):
        if name.upper().startswith("BUVIS_BIM_"):
            monkeypatch.delenv(name, raising=False)

    base = tmp_path.resolve()
    root = base / "vault"
    zettelkasten = root / "notes"
    folder = zettelkasten / "tiromex"
    folder.mkdir(parents=True)
    state_home = base / "state"
    state_home.mkdir()
    home = base / "home"
    home.mkdir()
    config_dir = base / "config"
    config_dir.mkdir()

    monkeypatch.setenv("BUVIS_BIM_PATH_ZETTELKASTEN", str(zettelkasten))
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("BUVIS_CONFIG_DIR", str(config_dir))
    return TxVault(
        root=root,
        zettelkasten=zettelkasten,
        folder=folder,
        state_home=state_home,
        home=home,
        config_dir=config_dir,
    )


def _date_for(note_id: str) -> str:
    return f"{note_id[0:4]}-{note_id[4:6]}-{note_id[6:8]}T{note_id[8:10]}:{note_id[10:12]}:{note_id[12:14]}+02:00"


def _front_matter(note_id: str, title: str, note_type: str, extra: str = "") -> str:
    return (
        "---\n"
        f"id: {note_id}\n"
        f'title: "{title}"\n'
        f"date: {_date_for(note_id)}\n"
        "tags: []\n"
        f"type: {note_type}\n"
        "publish: false\n"
        "processed: false\n"
        f"{extra}"
        "---\n"
    )


class TxNoteBuilder:
    """Build converted tiromex fixtures as text and write them into the vault."""

    def __init__(self, vault: TxVault) -> None:
        self.vault = vault
        self.prefix = vault.folder.relative_to(vault.root).as_posix()

    def concept(
        self,
        note_id: str = "20260411145300",
        title: str = "Knowledge is justified belief",
        *,
        concept_type: str = "thesis",
        claims: list[tuple[str, str]] | None = None,
        parent_id: str = "20260411140000",
        parent_title: str = "§ Epistemology",
        backmatter: list[str] | None = None,
    ) -> str:
        """Return a valid concept note with one parent link."""
        rows = [("c1", title)] if claims is None else claims
        extra = f"concept-type: {concept_type}\nassent: tentative\nlifecycle: fleeting\n"
        if rows:
            extra += "claims:\n" + "".join(
                f'  - id: {claim_id}\n    statement: "{statement}"\n' for claim_id, statement in rows
            )
        lines = [f"- parent:: [[{self.prefix}/{parent_id}|{parent_title}]]", *(backmatter or [])]
        return (
            _front_matter(note_id, title, "note", extra)
            + f"\n# {title}\n\nThe claim holds for ordinary cases.\n\n---\n\n"
            + "\n".join(lines)
            + "\n"
        )

    def index(
        self,
        note_id: str = "20260411140000",
        title: str = "§ Epistemology",
        *,
        members: list[tuple[str, str]] | None = None,
    ) -> str:
        """Return a valid index note with one members block."""
        rows = [("20260411145300", "Knowledge is justified belief")] if members is None else members
        block = "".join(f"- [[{self.prefix}/{member_id}|{member_title}]]\n" for member_id, member_title in rows)
        return (
            _front_matter(note_id, title, "index")
            + f"\n# {title}\n\nNotes on what knowledge is.\n\n"
            + "<!-- tx:members -->\n"
            + block
            + "<!-- /tx:members -->\n"
        )

    def run(self, note_id: str = "20260411150000", title: str = "Run 2026-04-11") -> str:
        """Return a valid ``tx-run`` note."""
        return _front_matter(note_id, title, "tx-run") + f"\n# {title}\n\nProcessed one source.\n"

    def plain(self, note_id: str = "20260411160000", title: str = "Shopping list") -> str:
        """Return a plain bim note with no tiromex fields."""
        return _front_matter(note_id, title, "note") + f"\n# {title}\n\nBuy bread.\n"

    def write(self, text: str, stem: str, folder: Path | None = None) -> Path:
        """Write ``text`` to ``<folder>/<stem>.md`` (default: the tiromex folder)."""
        target_dir = self.vault.folder if folder is None else folder
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{stem}.md"
        path.write_text(text, encoding="utf-8")
        return path


@pytest.fixture
def tx_notes(tx_vault: TxVault) -> TxNoteBuilder:
    return TxNoteBuilder(tx_vault)
