"""Tests for ``validate_tiromex``: reading the folder and the graph rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bim.commands.tx.shared.paths import TiromexPaths, resolve_tiromex
from bim.commands.tx.shared.validator import Diagnostic, validate_tiromex

if TYPE_CHECKING:
    from pathlib import Path

    from tests.tools.bim.tx.conftest import TxNoteBuilder, TxVault

INDEX_ID = "20260411140000"
A_ID = "20260411145300"
B_ID = "20260412090000"
C_ID = "20260413100000"
D_ID = "20260414110000"
TITLES = {
    A_ID: "Knowledge is justified belief",
    B_ID: "Belief needs grounds",
    C_ID: "Grounds need reasons",
    D_ID: "Reasons end somewhere",
}
OUTSIDE_LINK = "[[notes/private/hidden|Hidden]]"
DOUBT = 'doubts:\n  - mode: disagreement\n    claim: c1\n    rationale: "Gettier cases"\n'


def _rel(stem: str) -> str:
    return f"notes/tiromex/{stem}.md"


def _link(stem: str, title: str = "Linked") -> str:
    return f"[[notes/tiromex/{stem}|{title}]]"


def _found(paths: TiromexPaths, **kwargs: int) -> list[tuple[str, str]]:
    diagnostics = validate_tiromex(paths, **kwargs)
    assert all(isinstance(d, Diagnostic) for d in diagnostics)
    assert all(isinstance(d.message, str) and d.message.strip() for d in diagnostics)
    return [(d.path, d.rule) for d in diagnostics]


def _target(to: str) -> str:
    return DOUBT + f"    target:\n      to: {to}\n      claim: c2\n"


def _concept(tx_notes: TxNoteBuilder, note_id: str, *backmatter: str, extra: str = "", parent: str = INDEX_ID) -> Path:
    text = tx_notes.concept(note_id, TITLES[note_id], parent_id=parent, backmatter=list(backmatter))
    if extra:
        text = text.replace("processed: false\n", f"processed: false\n{extra}", 1)
    return tx_notes.write(text, note_id)


@pytest.fixture
def paths(tx_vault: TxVault) -> TiromexPaths:
    return resolve_tiromex(tx_vault.zettelkasten, "tiromex")


@pytest.fixture
def index(tx_notes: TxNoteBuilder) -> Path:
    return tx_notes.write(tx_notes.index(), INDEX_ID)


@pytest.fixture
def outside_note(tx_notes: TxNoteBuilder, tx_vault: TxVault) -> Path:
    """A real note outside the tiromex folder, at ``notes/private/hidden.md``."""
    return tx_notes.write(tx_notes.concept("20260101000000", "Private"), "hidden", tx_vault.zettelkasten / "private")


class TestReadsTheFolder:
    def test_empty_folder_gives_no_diagnostics(self, paths: TiromexPaths) -> None:
        assert validate_tiromex(paths) == []

    @pytest.mark.usefixtures("index")
    def test_valid_vault_gives_no_diagnostics(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID, f"- supports:: {_link(B_ID)}", f"- requires:: [[notes/tiromex/./{B_ID}|B]]")
        _concept(tx_notes, B_ID, f"- requires:: {_link(f'sub/{C_ID}')}")
        text = tx_notes.concept(C_ID, TITLES[C_ID], concept_type="question", claims=[])
        tx_notes.write(text, C_ID, paths.folder / "sub")
        tx_notes.write(tx_notes.run(), "20260411150000")
        tx_notes.write(tx_notes.plain(), "20260411160000")

        assert validate_tiromex(paths) == []

    @pytest.mark.usefixtures("index")
    def test_notes_outside_the_folder_are_not_validated(self, paths: TiromexPaths, tx_vault: TxVault) -> None:
        (tx_vault.zettelkasten / "loose.md").write_text("no front matter\n", encoding="utf-8")
        (tx_vault.root / "broken.md").write_text("no front matter\n", encoding="utf-8")

        assert validate_tiromex(paths) == []

    def test_validates_the_given_folder(self, paths: TiromexPaths, tx_notes: TxNoteBuilder, tx_vault: TxVault) -> None:
        tx_notes.write(tx_notes.index(), INDEX_ID)
        tx_notes.write("no front matter\n", "broken", tx_vault.zettelkasten / "atlas")
        atlas = resolve_tiromex(tx_vault.zettelkasten, "atlas")

        assert validate_tiromex(paths) == []
        assert _found(atlas) == [("notes/atlas/broken.md", "parse-error")]

    @pytest.mark.usefixtures("index")
    def test_max_body_lines_reaches_every_note(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID)

        assert _found(paths, max_body_lines=2) == [(_rel(INDEX_ID), "oversized-body")]
        assert _found(paths, max_body_lines=1) == [
            (_rel(INDEX_ID), "oversized-body"),
            (_rel(A_ID), "oversized-body"),
        ]
        assert _found(paths) == []

    def test_per_note_diagnostics_in_path_order_then_graph(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        tx_notes.write(tx_notes.index().replace("publish: false", "publish: true", 1), INDEX_ID)
        _concept(tx_notes, A_ID, f"- supports:: {_link(D_ID)}", extra="tags: [person]\n")
        text = tx_notes.concept(B_ID, TITLES[B_ID]).replace("publish: false", "publish: true", 1)
        tx_notes.write(text, B_ID)

        assert _found(paths) == [
            (_rel(INDEX_ID), "publish-true"),
            (_rel(A_ID), "forbidden-tag"),
            (_rel(B_ID), "publish-true"),
            (_rel(A_ID), "dangling-link"),
        ]


class TestParseError:
    @pytest.mark.usefixtures("index")
    @pytest.mark.parametrize(
        "content",
        [
            b"no front matter\n",
            b"---\ntitle: [unclosed\n---\n\n# T\n\nBody.\n",
            b"---\nid: 20260411170000\ntitle: T\n---\n\n# T\n\nA\n\n---\n\nB\n\n---\n\n- parent:: [[a|b]]\n",
            b"---\nid: 20260411170000\ntitle: \xff\xfe\n---\n\n# T\n",
        ],
    )
    def test_unreadable_or_unparseable_file(self, paths: TiromexPaths, content: bytes) -> None:
        (paths.folder / "broken.md").write_bytes(content)

        assert _found(paths) == [(_rel("broken"), "parse-error")]

    @pytest.mark.usefixtures("index")
    def test_rule_in_the_body_gives_parse_error_only(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        text = tx_notes.concept().replace("ordinary cases.\n", "ordinary cases.\n\n---\n\nMore prose.\n", 1)
        tx_notes.write(text, A_ID)

        assert _found(paths) == [(_rel(A_ID), "parse-error")]

    @pytest.mark.usefixtures("index")
    def test_broken_note_is_left_out_of_the_graph(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID, f"- requires:: {_link(B_ID)}")
        text = tx_notes.concept(B_ID, TITLES[B_ID], backmatter=[f"- requires:: {_link(A_ID)}"])
        tx_notes.write(text.replace("ordinary cases.\n", "ordinary cases.\n\n---\n\nMore.\n", 1), B_ID)

        assert _found(paths) == [(_rel(B_ID), "parse-error")]

    def test_broken_parent_file_is_still_a_file(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        (paths.folder / "broken.md").write_text("no front matter\n", encoding="utf-8")
        _concept(tx_notes, A_ID, parent="broken")

        assert _found(paths) == [(_rel("broken"), "parse-error")]


class TestPathConfinement:
    @pytest.mark.usefixtures("index", "outside_note")
    @pytest.mark.parametrize(
        "line",
        [
            f"- supports:: {OUTSIDE_LINK}",
            "- requires:: [[notes/tiromex/../private/hidden|Hidden]]",
            "- causes:: [[notes/tiromex-old/hidden|Hidden]]",
            f"- defines:: [[/notes/tiromex/{INDEX_ID}|Absolute]]",
        ],
    )
    def test_relation_outside_the_folder(self, paths: TiromexPaths, tx_notes: TxNoteBuilder, line: str) -> None:
        tx_notes.write(tx_notes.concept("20260101000000", "Old"), "hidden", paths.zettelkasten / "tiromex-old")
        _concept(tx_notes, A_ID, line)

        assert _found(paths) == [(_rel(A_ID), "path-confinement")]

    @pytest.mark.usefixtures("outside_note")
    def test_parent_outside_the_folder(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID, parent="../private/hidden")
        tx_notes.write(tx_notes.index() + f"\n---\n\n- parent:: {OUTSIDE_LINK}\n", INDEX_ID)

        assert sorted(_found(paths)) == [(_rel(INDEX_ID), "path-confinement"), (_rel(A_ID), "path-confinement")]

    @pytest.mark.usefixtures("index", "outside_note")
    def test_doubt_target_outside_the_folder(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID, extra=_target("notes/private/hidden.md"))

        assert _found(paths) == [(_rel(A_ID), "path-confinement")]

    @pytest.mark.usefixtures("index")
    def test_symlink_leaving_the_folder(self, paths: TiromexPaths, tx_notes: TxNoteBuilder, outside_note: Path) -> None:
        (paths.folder / "leak.md").symlink_to(outside_note)
        _concept(tx_notes, A_ID, "- supports:: [[notes/tiromex/leak|Leak]]")

        assert _found(paths) == [(_rel(A_ID), "path-confinement")]


class TestDangling:
    @pytest.mark.usefixtures("index")
    @pytest.mark.parametrize("relation", ["supports", "requires", "analogous-to", "narrower-than"])
    def test_dangling_link(self, paths: TiromexPaths, tx_notes: TxNoteBuilder, relation: str) -> None:
        _concept(tx_notes, A_ID, f"- {relation}:: {_link(B_ID)}")

        assert _found(paths) == [(_rel(A_ID), "dangling-link")]

    @pytest.mark.usefixtures("index")
    @pytest.mark.parametrize("relation", ["supports", "requires"])
    def test_missing_link_after_an_existing_one_dangles(
        self, paths: TiromexPaths, tx_notes: TxNoteBuilder, relation: str
    ) -> None:
        _concept(tx_notes, B_ID)
        _concept(tx_notes, A_ID, f"- {relation}:: {_link(B_ID, 'x')}, {_link(C_ID, 'y')}")

        assert _found(paths) == [(_rel(A_ID), "dangling-link")]

    @pytest.mark.usefixtures("index")
    def test_link_to_a_directory_dangles(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        (paths.folder / f"{B_ID}.md").mkdir()
        _concept(tx_notes, A_ID, f"- supports:: {_link(B_ID)}")

        assert _found(paths) == [(_rel(A_ID), "dangling-link")]

    @pytest.mark.usefixtures("index")
    def test_links_to_existing_notes_pass(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID, f"- supports:: {_link(B_ID)}, {_link(INDEX_ID)}", f"- causes:: {_link(f'sub/{C_ID}')}")
        _concept(tx_notes, B_ID)
        tx_notes.write(tx_notes.concept(C_ID, TITLES[C_ID]), C_ID, paths.folder / "sub")

        assert _found(paths) == []

    @pytest.mark.parametrize("parent", ["20260401000000", "20260411140001"])
    def test_dangling_moc(self, paths: TiromexPaths, tx_notes: TxNoteBuilder, parent: str) -> None:
        tx_notes.write(tx_notes.index() + f"\n---\n\n- parent:: {_link(parent, '§ Philosophy')}\n", INDEX_ID)
        _concept(tx_notes, A_ID)
        _concept(tx_notes, B_ID, parent=parent)

        assert sorted(_found(paths)) == [(_rel(INDEX_ID), "dangling-moc"), (_rel(B_ID), "dangling-moc")]

    @pytest.mark.usefixtures("index")
    def test_existing_parent_of_an_index_passes(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        tx_notes.write(tx_notes.index("20260411130000", "§ Philosophy", members=[]), "20260411130000")
        text = tx_notes.index("20260411135000", "§ Knowledge", members=[])
        tx_notes.write(text + f"\n---\n\n- parent:: {_link('20260411130000', '§ Philosophy')}\n", "20260411135000")

        assert _found(paths) == []

    @pytest.mark.usefixtures("index")
    @pytest.mark.parametrize("to", [f"notes/tiromex/{C_ID}.md", f"notes/tiromex/{B_ID}", "notes/tiromex/sub.md"])
    def test_dangling_doubt_target(self, paths: TiromexPaths, tx_notes: TxNoteBuilder, to: str) -> None:
        _concept(tx_notes, B_ID)
        (paths.folder / "sub.md").mkdir()
        _concept(tx_notes, A_ID, extra=_target(to))

        assert _found(paths) == [(_rel(A_ID), "dangling-doubt-target")]

    @pytest.mark.usefixtures("index")
    @pytest.mark.parametrize(
        "doubts", [_target(f"notes/tiromex/{B_ID}.md"), _target(f"notes/tiromex/./{B_ID}.md"), DOUBT]
    )
    def test_existing_or_absent_doubt_target_passes(
        self, paths: TiromexPaths, tx_notes: TxNoteBuilder, doubts: str
    ) -> None:
        _concept(tx_notes, B_ID)
        _concept(tx_notes, A_ID, extra=doubts)

        assert _found(paths) == []

    @pytest.mark.usefixtures("index", "outside_note")
    def test_malformed_target_gives_only_its_shape_rule(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID, extra=DOUBT + "    target: notes/private/hidden.md\n")

        assert _found(paths) == [(_rel(A_ID), "doubt-target-shape")]


class TestTransitiveCycle:
    @pytest.mark.usefixtures("index")
    @pytest.mark.parametrize("relation", ["requires", "broader-than", "narrower-than"])
    @pytest.mark.parametrize("edge", [B_ID, f"./{B_ID}"])
    def test_two_note_cycle_is_reported_once(
        self, paths: TiromexPaths, tx_notes: TxNoteBuilder, relation: str, edge: str
    ) -> None:
        _concept(tx_notes, A_ID, f"- {relation}:: {_link(edge)}")
        _concept(tx_notes, B_ID, f"- {relation}:: {_link(A_ID)}")

        found = _found(paths)

        assert [rule for _, rule in found] == ["transitive-cycle"]
        assert found[0][0] in {_rel(A_ID), _rel(B_ID)}

    @pytest.mark.usefixtures("index")
    def test_three_note_cycle_is_reported_on_a_member(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID, f"- requires:: {_link(B_ID)}")
        _concept(tx_notes, B_ID, f"- requires:: {_link(C_ID)}")
        _concept(tx_notes, C_ID, f"- requires:: [[notes/tiromex/./{A_ID}|A]]")
        _concept(tx_notes, D_ID, f"- requires:: {_link(A_ID)}")

        found = _found(paths)

        assert [rule for _, rule in found] == ["transitive-cycle"]
        assert found[0][0] in {_rel(A_ID), _rel(B_ID), _rel(C_ID)}

    @pytest.mark.usefixtures("index")
    def test_each_relation_is_reported_on_its_own(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID, f"- requires:: {_link(B_ID)}", f"- broader-than:: {_link(B_ID)}")
        _concept(tx_notes, B_ID, f"- requires:: {_link(A_ID)}", f"- broader-than:: {_link(A_ID)}")

        found = _found(paths)

        assert [rule for _, rule in found] == ["transitive-cycle", "transitive-cycle"]
        assert {path for path, _ in found} <= {_rel(A_ID), _rel(B_ID)}

    @pytest.mark.usefixtures("index")
    @pytest.mark.parametrize(
        ("a_line", "b_line"),
        [
            (f"- supports:: {_link(B_ID)}", f"- supports:: {_link(A_ID)}"),
            (f"- contradicts:: {_link(B_ID)}", f"- contradicts:: {_link(A_ID)}"),
            (f"- requires:: {_link(B_ID)}", f"- broader-than:: {_link(A_ID)}"),
            (f"- broader-than:: {_link(B_ID)}", f"- narrower-than:: {_link(A_ID)}"),
            (f"- requires:: {_link(B_ID)}", f"- requires:: {_link(C_ID)}"),
        ],
    )
    def test_no_cycle_within_one_transitive_relation(
        self, paths: TiromexPaths, tx_notes: TxNoteBuilder, a_line: str, b_line: str
    ) -> None:
        _concept(tx_notes, A_ID, a_line)
        _concept(tx_notes, B_ID, b_line)
        _concept(tx_notes, C_ID)

        assert _found(paths) == []

    def test_index_notes_are_not_graph_nodes(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        tx_notes.write(tx_notes.index() + f"\n---\n\n- requires:: {_link(A_ID)}\n", INDEX_ID)
        _concept(tx_notes, A_ID, f"- requires:: {_link(INDEX_ID)}")

        assert _found(paths) == []
