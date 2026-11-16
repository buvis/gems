"""Tests for the tiromex note format reader in ``bim.commands.tx.shared.format``."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest
from bim.commands.tx.shared.format import (
    ASSENT_VALUES,
    CLAIM_BEARING_CONCEPT_TYPES,
    CONCEPT_NOTE_TYPES,
    CONCEPT_TYPE_VALUES,
    DOUBT_MODE_VALUES,
    FORBIDDEN_TAGS,
    INDEX_TYPE,
    LIFECYCLE_VALUES,
    MEMBERS_CLOSE,
    MEMBERS_OPEN,
    MIRROR_PREFIX,
    RELATION_VALUES,
    TRANSITIVE_RELATIONS,
    TX_RUN_TYPE,
    Assent,
    ConceptType,
    DoubtMode,
    Lifecycle,
    NoteKind,
    Relation,
    WikiLink,
    as_datetime,
    body_lines,
    classify,
    format_links,
    h1_titles,
    link_file,
    parents,
    parse_links,
    parse_note,
    read_note,
    relations,
    serialize,
    sources,
)
from bim.commands.tx.shared.paths import resolve_tiromex
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

if TYPE_CHECKING:
    from tests.tools.bim.tx.conftest import TxNoteBuilder, TxVault

CONCEPT_PATH = "notes/tiromex/20260411145300.md"
RELATION_ORDER = [
    "supports",
    "contradicts",
    "exemplifies",
    "supersedes",
    "defines",
    "analogous-to",
    "causes",
    "requires",
    "broader-than",
    "narrower-than",
]


def _link(stem: str, title: str) -> WikiLink:
    return WikiLink(target=f"notes/tiromex/{stem}", title=title)


@pytest.fixture
def local_tz(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str], None]]:
    """Set the process local time zone (POSIX TZ string) for one test."""
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is not available on this platform")

    def set_zone(zone: str) -> None:
        monkeypatch.setenv("TZ", zone)
        time.tzset()

    yield set_zone
    monkeypatch.undo()
    time.tzset()


class TestVocabularies:
    def test_enums_hold_the_source_values_in_order(self) -> None:
        assert [m.value for m in ConceptType] == [
            "thesis",
            "argument",
            "aporia",
            "question",
            "example",
            "observation",
        ]
        assert [m.value for m in Assent] == ["accepted", "tentative", "rejected", "unknown"]
        assert [m.value for m in Lifecycle] == ["fleeting", "literature", "evergreen"]
        assert [m.value for m in DoubtMode] == [
            "disagreement",
            "regress",
            "context-relative",
            "assumption",
            "circular",
        ]
        assert [m.value for m in Relation] == RELATION_ORDER
        for enum in (ConceptType, Assent, Lifecycle, DoubtMode, Relation):
            assert all(isinstance(member, str) for member in enum)

    def test_value_sets_are_frozensets_of_the_enum_values(self) -> None:
        pairs = [
            (CONCEPT_TYPE_VALUES, ConceptType),
            (ASSENT_VALUES, Assent),
            (LIFECYCLE_VALUES, Lifecycle),
            (DOUBT_MODE_VALUES, DoubtMode),
            (RELATION_VALUES, Relation),
        ]
        for values, enum in pairs:
            assert isinstance(values, frozenset)
            assert values == frozenset(m.value for m in enum)
        assert "context-relative" in DOUBT_MODE_VALUES
        assert "context relative" not in DOUBT_MODE_VALUES
        assert "Thesis" not in CONCEPT_TYPE_VALUES
        assert "support" not in RELATION_VALUES
        assert 5 not in ASSENT_VALUES

    def test_constants_match_the_contract(self) -> None:
        assert TRANSITIVE_RELATIONS == ("requires", "broader-than", "narrower-than")
        assert CLAIM_BEARING_CONCEPT_TYPES == frozenset({"thesis", "argument", "observation"})
        assert isinstance(CLAIM_BEARING_CONCEPT_TYPES, frozenset)
        assert CONCEPT_NOTE_TYPES == (
            "note",
            "definition",
            "procedure",
            "wiki-article",
            "cheatsheet",
            "snippet",
            "course",
            "ai-prompt",
        )
        assert INDEX_TYPE == "index"
        assert TX_RUN_TYPE == "tx-run"
        assert FORBIDDEN_TAGS == frozenset({"person", "book"})
        assert MEMBERS_OPEN == "<!-- tx:members -->"
        assert MEMBERS_CLOSE == "<!-- /tx:members -->"
        assert MIRROR_PREFIX == "mirror:"

    def test_note_kind_values(self) -> None:
        assert [m.value for m in NoteKind] == ["concept", "index", "run", "plain"]


class TestClassify:
    @pytest.mark.parametrize(
        ("metadata", "expected"),
        [
            ({"concept-type": "thesis", "type": "note"}, NoteKind.CONCEPT),
            ({"concept-type": "nonsense", "type": "definition"}, NoteKind.CONCEPT),
            ({"concept-type": None, "type": "index"}, NoteKind.CONCEPT),
            ({"concept-type": "aporia", "type": "tx-run"}, NoteKind.CONCEPT),
            ({"type": "index"}, NoteKind.INDEX),
            ({"type": "index", "title": "§ Ethics"}, NoteKind.INDEX),
            ({"type": "tx-run"}, NoteKind.RUN),
            ({"type": "tx-run", "title": "Run"}, NoteKind.RUN),
            ({"type": "note"}, NoteKind.PLAIN),
            ({"concept_type": "thesis", "type": "note"}, NoteKind.PLAIN),
            ({"concept-types": "thesis"}, NoteKind.PLAIN),
            ({"type": "Index"}, NoteKind.PLAIN),
            ({"type": "index-old"}, NoteKind.PLAIN),
            ({"type": "tx-runs"}, NoteKind.PLAIN),
            ({"type": "run"}, NoteKind.PLAIN),
            ({}, NoteKind.PLAIN),
        ],
    )
    def test_classifies_by_concept_type_key_then_type(self, metadata: dict[str, object], expected: NoteKind) -> None:
        assert classify(ZettelData(metadata=metadata)) is expected


class TestParseNote:
    def test_body_runs_from_front_matter_to_the_backmatter_separator(self, tx_notes: TxNoteBuilder) -> None:
        text = tx_notes.concept().replace(
            "\n# Knowledge is justified belief\n",
            "\nIntro before heading.\n# Knowledge is justified belief\n",
        )

        note = parse_note(text, CONCEPT_PATH)

        assert note.path == CONCEPT_PATH
        assert note.kind is NoteKind.CONCEPT
        assert note.body == (
            "\nIntro before heading.\n# Knowledge is justified belief\n\nThe claim holds for ordinary cases.\n\n"
        )
        assert note.data.metadata["concept-type"] == "thesis"
        assert note.data.reference["parent"] == "[[notes/tiromex/20260411140000|§ Epistemology]]"

    def test_body_without_backmatter_runs_to_the_end(self, tx_notes: TxNoteBuilder) -> None:
        note = parse_note(tx_notes.run(), "notes/tiromex/sub/20260411150000.md")

        assert note.path == "notes/tiromex/sub/20260411150000.md"
        assert note.kind is NoteKind.RUN
        assert note.body == "\n# Run 2026-04-11\n\nProcessed one source.\n"
        assert note.data.reference == {}

    @pytest.mark.parametrize(
        ("build", "expected"),
        [
            ("concept", NoteKind.CONCEPT),
            ("index", NoteKind.INDEX),
            ("run", NoteKind.RUN),
            ("plain", NoteKind.PLAIN),
        ],
    )
    def test_classifies_each_fixture_kind(self, tx_notes: TxNoteBuilder, build: str, expected: NoteKind) -> None:
        assert parse_note(getattr(tx_notes, build)(), CONCEPT_PATH).kind is expected

    def test_a_dash_rule_that_is_not_exactly_three_dashes_stays_in_the_body(self, tx_notes: TxNoteBuilder) -> None:
        text = tx_notes.run().replace("Processed one source.\n", "Above.\n\n-----\n\nBelow.\n")

        note = parse_note(text, CONCEPT_PATH)

        assert body_lines(note.body) == ["# Run 2026-04-11", "Above.", "-----", "Below."]

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "# Title\n\nNo front matter here.\n",
            "Preface\n---\nid: 20260411145300\ntitle: T\ntype: note\n---\n\n# T\n\nBody.\n",
            "---\ntitle: [unclosed\ntype: note\n---\n\n# T\n\nBody.\n",
        ],
        ids=["empty", "no-front-matter", "front-matter-not-at-start", "broken-yaml"],
    )
    def test_rejects_text_without_a_readable_leading_front_matter(self, text: str) -> None:
        with pytest.raises(ValueError):
            parse_note(text, CONCEPT_PATH)

    def test_a_body_with_a_three_dash_rule_raises(self, tx_notes: TxNoteBuilder) -> None:
        text = tx_notes.run().replace("Processed one source.\n", "Above the rule.\n\n---\n\nBelow the rule is prose.\n")

        with pytest.raises(ValueError):
            parse_note(text, CONCEPT_PATH)


class TestReadNote:
    @pytest.mark.parametrize(
        ("folder_name", "stem", "kind"),
        [
            ("tiromex", "20260411145300", NoteKind.CONCEPT),
            ("atlas", "20260411140000", NoteKind.INDEX),
        ],
    )
    def test_records_the_vault_relative_path_and_kind(
        self, tx_vault: TxVault, tx_notes: TxNoteBuilder, folder_name: str, stem: str, kind: NoteKind
    ) -> None:
        folder = tx_vault.zettelkasten / folder_name
        text = tx_notes.concept(stem) if kind is NoteKind.CONCEPT else tx_notes.index(stem)
        file = tx_notes.write(text, stem, folder)
        paths = resolve_tiromex(tx_vault.zettelkasten, folder_name)

        note = read_note(paths, file)

        assert note.path == f"notes/{folder_name}/{stem}.md"
        assert note.kind is kind
        assert str(note.data.metadata["id"]) == stem
        assert note.body == parse_note(text, note.path).body

    def test_surfaces_a_parse_failure(self, tx_vault: TxVault, tx_notes: TxNoteBuilder) -> None:
        file = tx_notes.write("# Title\n\nNo front matter.\n", "20260411145300")

        with pytest.raises(ValueError):
            read_note(resolve_tiromex(tx_vault.zettelkasten, "tiromex"), file)


class TestParseLinks:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (
                "[[notes/tiromex/1|A]], [[notes/tiromex/2|B]]",
                [_link("1", "A"), _link("2", "B")],
            ),
            (
                ["[[notes/tiromex/3|C]]", "[[notes/tiromex/4|D]], [[notes/tiromex/5|E]]"],
                [_link("3", "C"), _link("4", "D"), _link("5", "E")],
            ),
            ("[[notes/tiromex/6|Belief, justified]]", [_link("6", "Belief, justified")]),
            (
                "[[notes/tiromex/7|Truth, belief, and warrant]], [[notes/tiromex/8|Gettier]]",
                [_link("7", "Truth, belief, and warrant"), _link("8", "Gettier")],
            ),
            ("[[notes/tiromex/9]]", [_link("9", "")]),
            ("see [[notes/tiromex/10|Ten]] here", [_link("10", "Ten")]),
            ("notes/tiromex/11", []),
            ("[notes/tiromex/12|Twelve]", []),
            ("", []),
            ([], []),
        ],
    )
    def test_finds_every_wikilink_without_splitting_on_commas(self, value: object, expected: list[WikiLink]) -> None:
        assert parse_links(value) == expected


class TestFormatLinks:
    def test_joins_links_with_comma_space(self) -> None:
        links = [_link("20260411145400", "Belief, justified"), _link("20260411145500", "Truth")]

        assert format_links(links) == (
            "[[notes/tiromex/20260411145400|Belief, justified]], [[notes/tiromex/20260411145500|Truth]]"
        )
        assert format_links([_link("1", "One")]) == "[[notes/tiromex/1|One]]"
        assert format_links([]) == ""

    def test_parse_links_reads_back_what_format_links_writes(self) -> None:
        links = [_link("1", "One, two"), _link("2", "§ Index"), _link("3", "Three")]

        assert parse_links(format_links(links)) == links

    def test_removes_quote_backslash_bracket_and_pipe_from_titles(self) -> None:
        link = _link("20260411145400", 'The "real" [x] a|b \\ c')

        assert format_links([link]) == "[[notes/tiromex/20260411145400|The real x ab  c]]"

    def test_a_cleaned_title_parses_where_a_raw_quote_does_not(self, tx_notes: TxNoteBuilder) -> None:
        link = _link("20260411145400", 'The "real" one')
        raw = tx_notes.concept(backmatter=['- supports:: [[notes/tiromex/20260411145400|The "real" one]]'])
        clean = tx_notes.concept(backmatter=[f"- supports:: {format_links([link])}"])

        with pytest.raises(ValueError):
            parse_note(raw, CONCEPT_PATH)
        note = parse_note(clean, CONCEPT_PATH)
        assert relations(note.data) == [("supports", _link("20260411145400", "The real one"))]


class TestRelationsAndParents:
    def test_reads_relation_keys_in_enum_order_one_tuple_per_link(self) -> None:
        data = ZettelData(
            reference={
                "narrower-than": "[[notes/tiromex/9|Nine]]",
                "parent": "[[notes/tiromex/0|§ Root]]",
                "supports": "[[notes/tiromex/1|One]], [[notes/tiromex/2|Two, too]]",
                "analogous-to": ["[[notes/tiromex/5|Five]]", "[[notes/tiromex/6|Six]]"],
                "support": "[[notes/tiromex/7|Seven]]",
                "requires-not": "[[notes/tiromex/8|Eight]]",
                "contradicts": "",
            },
            metadata={"requires": "[[notes/tiromex/4|Four]]"},
        )

        assert relations(data) == [
            ("supports", _link("1", "One")),
            ("supports", _link("2", "Two, too")),
            ("analogous-to", _link("5", "Five")),
            ("analogous-to", _link("6", "Six")),
            ("narrower-than", _link("9", "Nine")),
        ]

    def test_relation_order_follows_the_enum_not_the_note(self) -> None:
        data = ZettelData(reference={"causes": "[[notes/tiromex/3|Three]]", "defines": "[[notes/tiromex/4|Four]]"})

        assert relations(data) == [("defines", _link("4", "Four")), ("causes", _link("3", "Three"))]
        assert relations(ZettelData()) == []

    def test_reads_comma_and_repeated_key_forms_from_a_parsed_note(self, tx_notes: TxNoteBuilder) -> None:
        text = tx_notes.concept(
            backmatter=[
                "- supports:: [[notes/tiromex/20260411145400|Belief, justified]], [[notes/tiromex/20260411145500|B]]",
                "- contradicts:: [[notes/tiromex/20260411145600|C]]",
                "- contradicts:: [[notes/tiromex/20260411145700|D]]",
            ]
        )

        data = parse_note(text, CONCEPT_PATH).data

        assert relations(data) == [
            ("supports", _link("20260411145400", "Belief, justified")),
            ("supports", _link("20260411145500", "B")),
            ("contradicts", _link("20260411145600", "C")),
            ("contradicts", _link("20260411145700", "D")),
        ]
        assert parents(data) == [_link("20260411140000", "§ Epistemology")]

    @pytest.mark.parametrize(
        ("reference", "expected"),
        [
            (
                {"parent": "[[notes/tiromex/1|§ A]], [[notes/tiromex/2|§ B, C]]"},
                [_link("1", "§ A"), _link("2", "§ B, C")],
            ),
            (
                {"parent": ["[[notes/tiromex/3|§ D]]", "[[notes/tiromex/4|§ E]]"]},
                [_link("3", "§ D"), _link("4", "§ E")],
            ),
            ({"parents": "[[notes/tiromex/5|§ F]]", "supports": "[[notes/tiromex/6|G]]"}, []),
            ({}, []),
        ],
    )
    def test_parents_reads_only_the_parent_key(self, reference: dict[str, object], expected: list[WikiLink]) -> None:
        assert parents(ZettelData(reference=reference)) == expected

    @pytest.mark.parametrize(
        ("target", "expected"),
        [
            ("notes/tiromex/20260411145300", "notes/tiromex/20260411145300.md"),
            ("notes/atlas/20260411140000", "notes/atlas/20260411140000.md"),
            ("notes/tiromex/a.md", "notes/tiromex/a.md.md"),
            ("notes/tiromex/a#heading", "notes/tiromex/a#heading.md"),
        ],
    )
    def test_link_file_appends_md_without_normalising(self, target: str, expected: str) -> None:
        assert link_file(target) == expected


class TestSources:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("mirror:articles/2026/a.md", ["mirror:articles/2026/a.md"]),
            ("mirror:articles/a.md, mirror:books/b.md", ["mirror:articles/a.md", "mirror:books/b.md"]),
            ("mirror:a/x.md,mirror:b/y.md", ["mirror:a/x.md", "mirror:b/y.md"]),
            ("  mirror:a/x.md ,   mirror:b/y.md  ", ["mirror:a/x.md", "mirror:b/y.md"]),
            ("mirror:a/x.md, mirror:b/y.md, mirror:c/z.md", ["mirror:a/x.md", "mirror:b/y.md", "mirror:c/z.md"]),
            ("Smith, J. 2020", ["Smith, J. 2020"]),
            ("mirror:a/x.md, mirrors:b/y.md", ["mirror:a/x.md, mirrors:b/y.md"]),
            ("https://example.org/a", ["https://example.org/a"]),
            (["mirror:a/x.md, mirror:b/y.md", "mirror:c/z.md"], ["mirror:a/x.md", "mirror:b/y.md", "mirror:c/z.md"]),
            ([], []),
        ],
    )
    def test_splits_before_each_later_mirror_prefix(self, value: object, expected: list[str]) -> None:
        assert sources(ZettelData(reference={"source": value})) == expected

    def test_reads_only_the_source_key(self) -> None:
        assert sources(ZettelData(reference={"sources": "mirror:a/x.md"})) == []
        assert sources(ZettelData()) == []

    def test_reads_sources_from_a_parsed_note(self, tx_notes: TxNoteBuilder) -> None:
        text = tx_notes.concept(backmatter=["- source:: mirror:articles/a.md, mirror:books/b.md"])

        assert sources(parse_note(text, CONCEPT_PATH).data) == ["mirror:articles/a.md", "mirror:books/b.md"]


class TestBodyHelpers:
    def test_h1_titles_match_only_line_start_single_hash_headings(self) -> None:
        body = (
            "# First title\n\nI write C# and F# code.\n## Sub heading\n#NoSpace\n#\n#   \n"
            "  # Indented\n#\tTabbed title  \n# Last line"
        )

        assert h1_titles(body) == ["First title", "Tabbed title", "Last line"]
        assert h1_titles("# Only\n") == ["Only"]
        assert h1_titles("Just text.\n") == []
        assert h1_titles("") == []

    def test_body_lines_keeps_non_blank_lines_with_the_h1(self) -> None:
        body = "\n# T\n\nI write C# and F# code.\n   \n\t\nsecond line\n"

        assert body_lines(body) == ["# T", "I write C# and F# code.", "second line"]
        assert body_lines("\n\n  \n") == []
        assert body_lines("") == []

    def test_helpers_read_the_raw_body_of_a_parsed_note(self, tx_notes: TxNoteBuilder) -> None:
        text = tx_notes.concept(title="Typed languages").replace(
            "\n# Typed languages\n\nThe claim holds for ordinary cases.\n",
            "\nIntro line.\n# Typed languages\n\nI write C# and F# code.\n",
        )

        note = parse_note(text, CONCEPT_PATH)

        assert h1_titles(note.body) == ["Typed languages"]
        assert body_lines(note.body) == ["Intro line.", "# Typed languages", "I write C# and F# code."]


class TestAsDatetime:
    @pytest.mark.parametrize(
        "value",
        [
            datetime(2026, 4, 11, 14, 53, tzinfo=timezone(timedelta(hours=2))),
            datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=-7))),
        ],
    )
    def test_aware_datetime_is_returned_unchanged(self, local_tz: Callable[[str], None], value: datetime) -> None:
        local_tz("IST-5:30")

        result = as_datetime(value)

        assert result == value
        assert result is not None
        assert result.utcoffset() == value.utcoffset()

    @pytest.mark.parametrize(
        ("zone", "offset"),
        [("IST-5:30", timedelta(hours=5, minutes=30)), ("BRT3", timedelta(hours=-3))],
    )
    def test_naive_values_get_the_local_zone(
        self, local_tz: Callable[[str], None], zone: str, offset: timedelta
    ) -> None:
        local_tz(zone)
        cases = [
            (datetime(2026, 4, 11, 14, 53), datetime(2026, 4, 11, 14, 53)),
            (date(2026, 4, 11), datetime(2026, 4, 11)),
            (date(2025, 12, 31), datetime(2025, 12, 31)),
            ("2026-04-11T14:53:00", datetime(2026, 4, 11, 14, 53)),
            ("2025-12-31", datetime(2025, 12, 31)),
        ]

        for value, wall_clock in cases:
            result = as_datetime(value)
            assert result is not None, value
            assert result.utcoffset() == offset, value
            assert result.replace(tzinfo=None) == wall_clock, value

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2026-04-11T14:53:00+02:00", datetime(2026, 4, 11, 14, 53, tzinfo=timezone(timedelta(hours=2)))),
            ("2025-01-02T03:04:05-07:00", datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=-7)))),
        ],
    )
    def test_aware_iso_string_keeps_its_offset(
        self, local_tz: Callable[[str], None], value: str, expected: datetime
    ) -> None:
        local_tz("IST-5:30")

        result = as_datetime(value)

        assert result == expected
        assert result is not None
        assert result.utcoffset() == expected.utcoffset()

    @pytest.mark.parametrize(
        "value",
        ["yesterday", "", "2026-13-01", "2026-04-11T25:00:00", 20260411145300, 1.5, None, ["2026-04-11"]],
    )
    def test_unreadable_values_give_none(self, value: object) -> None:
        assert as_datetime(value) is None

    def test_reads_a_parsed_front_matter_date(self, tx_notes: TxNoteBuilder) -> None:
        note = parse_note(tx_notes.concept(), CONCEPT_PATH)

        assert as_datetime(note.data.metadata["date"]) == datetime(
            2026, 4, 11, 14, 53, tzinfo=timezone(timedelta(hours=2))
        )


def _concept_with_relations(tx_notes: TxNoteBuilder) -> str:
    text = tx_notes.concept(
        backmatter=[
            "- supports:: [[notes/tiromex/20260411145400|Belief, justified]], [[notes/tiromex/20260411145500|Truth]]",
            "- requires:: [[notes/tiromex/20260411145600|Evidence]]",
        ]
    )
    return text.replace("lifecycle: fleeting\n", "lifecycle: fleeting\nlens: epistemic\nx-weight: 3\n")


class TestSerialize:
    @pytest.mark.parametrize(
        ("build", "kind"),
        [
            (_concept_with_relations, NoteKind.CONCEPT),
            (lambda notes: notes.index(), NoteKind.INDEX),
            (lambda notes: notes.run(), NoteKind.RUN),
        ],
        ids=["concept", "index", "tx-run"],
    )
    def test_round_trip_keeps_metadata_reference_and_body(
        self, tx_notes: TxNoteBuilder, build: Callable[[TxNoteBuilder], str], kind: NoteKind
    ) -> None:
        note = parse_note(build(tx_notes), CONCEPT_PATH)

        again = parse_note(serialize(note.data), CONCEPT_PATH)

        assert note.kind is kind
        assert again.kind is kind
        assert again.data.metadata == note.data.metadata
        assert again.data.reference == note.data.reference
        assert h1_titles(again.body) == h1_titles(note.body)
        assert len(h1_titles(note.body)) == 1
        assert body_lines(again.body) == body_lines(note.body)
        assert len(body_lines(note.body)) >= 2

    def test_concept_round_trip_keeps_unknown_keys_and_relations(self, tx_notes: TxNoteBuilder) -> None:
        note = parse_note(_concept_with_relations(tx_notes), CONCEPT_PATH)

        again = parse_note(serialize(note.data), CONCEPT_PATH)

        assert again.data.metadata["lens"] == "epistemic"
        assert again.data.metadata["x-weight"] == 3
        assert relations(again.data) == [
            ("supports", _link("20260411145400", "Belief, justified")),
            ("supports", _link("20260411145500", "Truth")),
            ("requires", _link("20260411145600", "Evidence")),
        ]

    def test_writes_bim_key_order_then_other_keys_in_insertion_order(self) -> None:
        data = ZettelData(
            metadata={
                "lens": "epistemic",
                "processed": False,
                "concept-type": "thesis",
                "title": "T",
                "tags": ["alpha"],
                "id": 20260411145300,
                "publish": False,
                "type": "note",
                "date": datetime(2026, 4, 11, 14, 53, tzinfo=timezone(timedelta(hours=2))),
                "x-extra": 3,
            },
            reference={"supports": "[[notes/tiromex/1|A]], [[notes/tiromex/2|B]]"},
            sections=[("# T", "\nBody line.\n")],
        )

        text = serialize(data)

        front = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
        assert front is not None
        keys = re.findall(r"^([a-z][a-z-]*):", front.group(1), re.MULTILINE)
        assert keys == [
            "id",
            "title",
            "date",
            "tags",
            "type",
            "publish",
            "processed",
            "lens",
            "concept-type",
            "x-extra",
        ]
        assert "\n- supports:: [[notes/tiromex/1|A]], [[notes/tiromex/2|B]]\n" in text
