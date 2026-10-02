"""Vault-level validation: graph rules and the transitive-cycle check."""

from __future__ import annotations

from pathlib import Path

from buvis.pybase.filesystem import atomic_write_text
from klyreon.spec.validator import validate_vault


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, text)


def _zettel_text(zid: str, title: str, *, body: str | None = None, extra: str = "") -> str:
    body = body if body is not None else f"\n# {title}\n"
    return f'---\nid: "{zid}"\ntitle: {title}\ncreated: "{_created(zid)}"\ntype: note\n{extra}---\n{body}'


def _created(zid: str) -> str:
    return f"{zid[0:4]}-{zid[4:6]}-{zid[6:8]}T{zid[8:10]}:{zid[10:12]}:{zid[12:14]}+02:00"


def _rules(root: Path) -> list[str]:
    return [e.rule for e in validate_vault(root)]


def _write_moc(root: Path, slug: str = "a") -> None:
    text = f'---\nid: {slug}\ntitle: A\ncreated: "2026-01-01T00:00:00+02:00"\nkind: moc\n---\n\n# A\n'
    _write(root, f"wiki/mocs/{slug}.md", text)


class TestVaultGraphRules:
    def test_clean_corpus(self, valid_corpus: Path) -> None:
        assert validate_vault(valid_corpus) == []

    def test_dangling_source(self, empty_vault: Path) -> None:
        _write(
            empty_vault,
            "wiki/notes/20260101000000.md",
            _zettel_text("20260101000000", "T", extra="sources:\n- sources/archive/2026-01/missing.md\n"),
        )
        assert "dangling-source" in _rules(empty_vault)

    def test_dangling_moc(self, empty_vault: Path) -> None:
        _write(
            empty_vault,
            "wiki/notes/20260101000000.md",
            _zettel_text("20260101000000", "T", extra="mocs:\n- wiki/mocs/nope.md\n"),
        )
        assert "dangling-moc" in _rules(empty_vault)

    def test_dangling_link(self, empty_vault: Path) -> None:
        _write(
            empty_vault,
            "wiki/notes/20260101000000.md",
            _zettel_text(
                "20260101000000",
                "T",
                extra="mocs:\n- wiki/mocs/a.md\nlinks:\n- rel: supports\n  to: wiki/notes/20991231235959.md\n",
            ),
        )
        _write_moc(empty_vault)
        assert "dangling-link" in _rules(empty_vault)

    def test_dangling_doubt_target(self, empty_vault: Path) -> None:
        _write(
            empty_vault,
            "wiki/notes/20260101000000.md",
            _zettel_text(
                "20260101000000",
                "T",
                extra=(
                    "mocs:\n- wiki/mocs/a.md\nconcept-type: thesis\nassent: tentative\nlifecycle: fleeting\n"
                    "claims:\n- id: c1\n  statement: s\n"
                    "doubts:\n- mode: disagreement\n  claim: c1\n  rationale: r\n"
                    "  target:\n    to: wiki/notes/20991231235959.md\n    claim: c1\n"
                ),
            ),
        )
        _write_moc(empty_vault)
        assert "dangling-doubt-target" in _rules(empty_vault)

    def test_link_to_source_document(self, empty_vault: Path) -> None:
        _write(
            empty_vault,
            "sources/2026-01/article-x.md",
            '---\nid: article-x\ntitle: X\ncreated: "2026-01-01T00:00:00+02:00"\ntype: article\n---\n\n# X\n',
        )
        _write_moc(empty_vault)
        _write(
            empty_vault,
            "wiki/notes/20260101000000.md",
            _zettel_text(
                "20260101000000",
                "T",
                extra="mocs:\n- wiki/mocs/a.md\nlinks:\n- rel: supports\n  to: sources/2026-01/article-x.md\n",
            ),
        )
        assert "link-to-source" in _rules(empty_vault)

    def test_confinement_via_dotdot(self, empty_vault: Path) -> None:
        _write(
            empty_vault,
            "wiki/notes/20260101000000.md",
            _zettel_text("20260101000000", "T", extra="sources:\n- ../../etc/passwd\n"),
        )
        assert "path-confinement" in _rules(empty_vault)

    def test_three_hop_broader_than_cycle(self, empty_vault: Path) -> None:
        chain = {
            "20260101000001": "20260101000002",
            "20260101000002": "20260101000003",
            "20260101000003": "20260101000001",
        }
        _write_moc(empty_vault)
        for src, dst in chain.items():
            extra = f"mocs:\n- wiki/mocs/a.md\nlinks:\n- rel: broader-than\n  to: wiki/notes/{dst}.md\n"
            _write(empty_vault, f"wiki/notes/{src}.md", _zettel_text(src, "T", extra=extra))
        assert "transitive-cycle" in _rules(empty_vault)

    def test_legacy_colon_tag(self, empty_vault: Path) -> None:
        _write(
            empty_vault,
            "wiki/notes/20260101000000.md",
            _zettel_text("20260101000000", "T", extra="tags:\n- topos:self\n"),
        )
        assert "legacy-colon-tag" in _rules(empty_vault)

    def test_orphan_concept(self, empty_vault: Path) -> None:
        _write(
            empty_vault,
            "wiki/notes/20260101000000.md",
            _zettel_text(
                "20260101000000",
                "T",
                extra=(
                    "concept-type: thesis\nassent: tentative\nlifecycle: fleeting\nclaims:\n- id: c1\n  statement: s\n"
                ),
            ),
        )
        assert "orphan-concept" in _rules(empty_vault)

    def test_oversized_body(self, empty_vault: Path) -> None:
        body = "\n# T\n" + "\n".join(f"line {i}" for i in range(70))
        _write(empty_vault, "wiki/notes/20260101000000.md", _zettel_text("20260101000000", "T", body=body))
        assert "oversized-body" in [e.rule for e in validate_vault(empty_vault, max_body_lines=60)]

    def test_stale_review(self, empty_vault: Path) -> None:
        _write(
            empty_vault,
            "wiki/notes/20260101000000.md",
            _zettel_text(
                "20260101000000",
                "T",
                extra='updated: "2026-02-01T00:00:00+02:00"\nreviewed: "2026-01-15T00:00:00+02:00"\n',
            ),
        )
        assert "stale-review" in _rules(empty_vault)
