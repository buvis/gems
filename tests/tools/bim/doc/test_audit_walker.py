"""Unit tests for ``walk_business_root``.

The walker is a pure generator that scans a business root directory and
yields ``(folder_slug, pdf_path)`` tuples for each PDF, skipping audit-
irrelevant subtrees (`_triage/`, `<issuer>/inbox/`, hidden dirs).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bim.commands.doc.audit.walker import walk_business_root


@pytest.fixture
def business_root(tmp_path: Path) -> Path:
    """Build the canonical layout described in the PRD task."""
    root = tmp_path / "business"
    root.mkdir()

    cez = root / "cez-as"
    cez.mkdir()
    (cez / "20260101000000-cez-as-x.invoice.pdf").touch()
    (cez / "20260101000001-cez-as-y.invoice.pdf").touch()
    (cez / "notes.txt").touch()

    sub = cez / "sub"
    sub.mkdir()
    (sub / "20260101000002-cez-as-z.statement.pdf").touch()

    inbox = cez / "inbox"
    inbox.mkdir()
    (inbox / "pending.pdf").touch()

    o2 = root / "o2-czech"
    o2.mkdir()
    (o2 / "20260101000003-o2-czech-a.invoice.pdf").touch()

    triage = root / "_triage"
    triage.mkdir()
    (triage / "foo.pdf").touch()

    hidden = root / ".DS_Store"
    hidden.mkdir()
    (hidden / "bar.pdf").touch()

    (root / "toplevel.pdf").touch()

    return root


class TestWalkBusinessRoot:
    def test_yields_only_pdfs(self, business_root: Path) -> None:
        results = list(walk_business_root(business_root))
        paths = [p for _, p in results]
        assert all(p.suffix.lower() == ".pdf" for p in paths)
        assert not any(p.name == "notes.txt" for p in paths)

    def test_skips_triage_subtree(self, business_root: Path) -> None:
        results = list(walk_business_root(business_root))
        paths = [p for _, p in results]
        assert not any("_triage" in p.parts for p in paths)

    def test_skips_inbox_subtree(self, business_root: Path) -> None:
        results = list(walk_business_root(business_root))
        paths = [p for _, p in results]
        assert not any("inbox" in p.parts for p in paths)

    def test_skips_hidden_dirs(self, business_root: Path) -> None:
        results = list(walk_business_root(business_root))
        paths = [p for _, p in results]
        assert not any(".DS_Store" in p.parts for p in paths)

    def test_recurses_into_issuer_subdirs(self, business_root: Path) -> None:
        results = list(walk_business_root(business_root))
        slug_names = [(slug, p.name) for slug, p in results]
        assert (
            "cez-as",
            "20260101000002-cez-as-z.statement.pdf",
        ) in slug_names

    def test_yields_toplevel_files_with_empty_slug(self, business_root: Path) -> None:
        results = list(walk_business_root(business_root))
        toplevel = [(slug, p) for slug, p in results if p.name == "toplevel.pdf"]
        assert len(toplevel) == 1
        assert toplevel[0][0] == ""
        assert toplevel[0][1] == business_root / "toplevel.pdf"

    def test_deterministic_ordering(self, business_root: Path) -> None:
        first = list(walk_business_root(business_root))
        second = list(walk_business_root(business_root))
        assert first == second

    def test_case_insensitive_pdf_suffix(self, tmp_path: Path) -> None:
        root = tmp_path / "business"
        root.mkdir()
        issuer = root / "acme"
        issuer.mkdir()
        upper = issuer / "Foo.PDF"
        upper.touch()

        results = list(walk_business_root(root))
        assert ("acme", upper) in results

    def test_empty_business_root_yields_nothing(self, tmp_path: Path) -> None:
        root = tmp_path / "business"
        root.mkdir()
        assert list(walk_business_root(root)) == []

    def test_nonexistent_business_root_yields_empty(self, tmp_path: Path) -> None:
        root = tmp_path / "does-not-exist"
        assert list(walk_business_root(root)) == []
