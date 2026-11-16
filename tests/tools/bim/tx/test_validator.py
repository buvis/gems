"""Tests for the per-note rules of the tiromex mechanical validator (``validate_note``)."""

from __future__ import annotations

import dataclasses
import re
import time
from typing import TYPE_CHECKING

import pytest
from bim.commands.tx.shared.format import MEMBERS_CLOSE, MEMBERS_OPEN, parse_note
from bim.commands.tx.shared.validator import Diagnostic, validate_note

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tests.tools.bim.tx.conftest import TxNoteBuilder

CONCEPT_ID = "20260411145300"
INDEX_ID = "20260411140000"
RUN_ID = "20260411150000"
PLAIN_ID = "20260411160000"
CONCEPT_TITLE = "Knowledge is justified belief"
CLAIMS_BLOCK = f'claims:\n  - id: c1\n    statement: "{CONCEPT_TITLE}"\n'
BODY_LINE = "The claim holds for ordinary cases.\n"
LINK = "notes/tiromex/20260412090000"
DOUBT = 'doubts:\n  - mode: disagreement\n    claim: c1\n    rationale: "Gettier cases"\n'
TARGET = "    target:\n      to: notes/tiromex/20260412090000.md\n      claim: c2\n"
STEMS = {"concept": CONCEPT_ID, "index": INDEX_ID, "run": RUN_ID, "plain": PLAIN_ID}
TIROMEX_KINDS = ["concept", "index", "run"]


def _path(stem: str) -> str:
    return f"notes/tiromex/{stem}.md"


def _swap(text: str, old: str, new: str) -> str:
    assert old in text, f"fixture lacks {old!r}"
    return text.replace(old, new, 1)


def _with_front(text: str, extra: str) -> str:
    return _swap(text, "processed: false\n", f"processed: false\n{extra}")


def _note(tx_notes: TxNoteBuilder, kind: str) -> str:
    builders: dict[str, Callable[[], str]] = {
        "concept": tx_notes.concept,
        "index": tx_notes.index,
        "run": tx_notes.run,
        "plain": tx_notes.plain,
    }
    return builders[kind]()


def _rules(text: str, stem: str = CONCEPT_ID, **kwargs: int) -> list[str]:
    diagnostics = validate_note(parse_note(text, _path(stem)), **kwargs)
    assert all(isinstance(d, Diagnostic) for d in diagnostics)
    assert all(isinstance(d.message, str) and d.message.strip() for d in diagnostics)
    assert {d.path for d in diagnostics} <= {_path(stem)}
    return [d.rule for d in diagnostics]


@pytest.fixture
def set_zone() -> Iterator[Callable[[str], None]]:
    """Switch the process local timezone for one test and restore it after."""
    with pytest.MonkeyPatch.context() as patch:

        def apply(zone: str) -> None:
            patch.setenv("TZ", zone)
            time.tzset()

        yield apply
    time.tzset()


class TestDiagnostic:
    def test_keeps_fields_and_line_defaults_to_none(self) -> None:
        first = Diagnostic("notes/tiromex/a.md", "publish-true", "publish is true")
        second = Diagnostic(path="notes/tiromex/b.md", rule="empty-body", message="no body", line=7)

        assert (first.path, first.rule, first.message, first.line) == (
            "notes/tiromex/a.md",
            "publish-true",
            "publish is true",
            None,
        )
        assert (second.path, second.rule, second.message, second.line) == (
            "notes/tiromex/b.md",
            "empty-body",
            "no body",
            7,
        )

    @pytest.mark.parametrize("field", ["path", "rule", "message", "line"])
    def test_is_frozen(self, field: str) -> None:
        diagnostic = Diagnostic("notes/tiromex/a.md", "publish-true", "publish is true")

        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(diagnostic, field, "other")
        assert diagnostic == Diagnostic("notes/tiromex/a.md", "publish-true", "publish is true")


class TestValidFixtures:
    @pytest.mark.parametrize("kind", ["concept", "index", "run", "plain"])
    def test_builder_fixture_has_no_diagnostics(self, tx_notes: TxNoteBuilder, kind: str) -> None:
        assert _rules(_note(tx_notes, kind), STEMS[kind]) == []

    def test_second_set_of_fixtures_has_no_diagnostics(self, tx_notes: TxNoteBuilder) -> None:
        concept = tx_notes.concept("20260412090000", "Belief needs grounds", concept_type="argument")
        index = tx_notes.index("20260412080000", "§ Ethics", members=[])
        run = tx_notes.run("20260413100000", "Run 2026-04-13")
        plain = tx_notes.plain("20260414110000", "Errands")

        assert _rules(concept, "20260412090000") == []
        assert _rules(index, "20260412080000") == []
        assert _rules(run, "20260413100000") == []
        assert _rules(plain, "20260414110000") == []


class TestRequiredField:
    @pytest.mark.parametrize("field", ["id", "title", "date", "type"])
    @pytest.mark.parametrize("mode", ["missing", "empty", "blank"])
    def test_missing_or_blank_base_field(self, tx_notes: TxNoteBuilder, field: str, mode: str) -> None:
        replacement = {"missing": "", "empty": f'{field}: ""\n', "blank": f'{field}: "   "\n'}[mode]
        text, count = re.subn(rf"^{field}: .*\n", replacement, tx_notes.plain(), count=1, flags=re.MULTILINE)
        assert count == 1

        assert _rules(text, PLAIN_ID) == ["required-field"]

    def test_message_names_the_missing_field(self, tx_notes: TxNoteBuilder) -> None:
        messages: dict[str, str] = {}
        for field in ("id", "title", "date", "type"):
            text, count = re.subn(rf"^{field}: .*\n", "", tx_notes.plain(), count=1, flags=re.MULTILINE)
            assert count == 1
            diagnostics = validate_note(parse_note(text, _path(PLAIN_ID)))
            assert [d.rule for d in diagnostics] == ["required-field"]
            messages[field] = diagnostics[0].message

        for field, message in messages.items():
            assert re.search(rf"\b{field}\b", message), (field, message)
        assert len(set(messages.values())) == len(messages)

    @pytest.mark.parametrize("kind", TIROMEX_KINDS)
    def test_missing_date_on_every_kind(self, tx_notes: TxNoteBuilder, kind: str) -> None:
        text, count = re.subn(r"^date: .*\n", "", _note(tx_notes, kind), count=1, flags=re.MULTILINE)
        assert count == 1

        assert _rules(text, STEMS[kind]) == ["required-field"]


class TestPublishAndTags:
    @pytest.mark.parametrize(("kind", "expected"), [*((k, ["publish-true"]) for k in TIROMEX_KINDS), ("plain", [])])
    def test_publish_true(self, tx_notes: TxNoteBuilder, kind: str, expected: list[str]) -> None:
        text = _swap(_note(tx_notes, kind), "publish: false", "publish: true")

        assert _rules(text, STEMS[kind]) == expected

    @pytest.mark.parametrize("kind", TIROMEX_KINDS)
    @pytest.mark.parametrize(
        "tags", ['["topic:knowledge"]', '[knowledge, "area:epistemology"]', '["status:draft"]', '["x:y", knowledge]']
    )
    def test_legacy_colon_tag(self, tx_notes: TxNoteBuilder, kind: str, tags: str) -> None:
        text = _swap(_note(tx_notes, kind), "tags: []", f"tags: {tags}")

        assert _rules(text, STEMS[kind]) == ["legacy-colon-tag"]

    @pytest.mark.parametrize("kind", TIROMEX_KINDS)
    @pytest.mark.parametrize("tags", ["[person]", "[knowledge, book]"])
    def test_forbidden_tag(self, tx_notes: TxNoteBuilder, kind: str, tags: str) -> None:
        text = _swap(_note(tx_notes, kind), "tags: []", f"tags: {tags}")

        assert _rules(text, STEMS[kind]) == ["forbidden-tag"]

    @pytest.mark.parametrize("tags", ["[topic-knowledge, knowledge]", "[persona, books, notebook, person-of-interest]"])
    def test_near_miss_tags_pass(self, tx_notes: TxNoteBuilder, tags: str) -> None:
        assert _rules(_swap(tx_notes.concept(), "tags: []", f"tags: {tags}")) == []

    def test_plain_note_ignores_tag_rules(self, tx_notes: TxNoteBuilder) -> None:
        text = _swap(tx_notes.plain(), "tags: []", 'tags: [person, "topic:x"]')

        assert _rules(text, PLAIN_ID) == []


class TestHeadings:
    @pytest.mark.parametrize(
        ("kind", "old", "new"),
        [
            ("concept", BODY_LINE, BODY_LINE + "\n# Another heading\n"),
            ("concept", f"# {CONCEPT_TITLE}\n", ""),
            ("concept", f"# {CONCEPT_TITLE}\n", f"## {CONCEPT_TITLE}\n"),
            ("index", "Notes on what knowledge is.\n", "# Epistemology again\n"),
            ("run", "# Run 2026-04-11\n", ""),
        ],
    )
    def test_h1_exactly_one(self, tx_notes: TxNoteBuilder, kind: str, old: str, new: str) -> None:
        text = _swap(_note(tx_notes, kind), old, new)

        assert _rules(text, STEMS[kind]) == ["h1-exactly-one"]

    @pytest.mark.parametrize(
        "line", ["I write C# and F# code.", "#hashtag at line start", "  # indented hash", "#no-space heading"]
    )
    def test_hash_lines_that_are_not_h1_pass(self, tx_notes: TxNoteBuilder, line: str) -> None:
        text = _swap(tx_notes.concept(), BODY_LINE, f"{BODY_LINE}{line}\n")

        assert _rules(text) == []

    @pytest.mark.parametrize(
        ("kind", "old", "new"),
        [
            ("concept", f"# {CONCEPT_TITLE}\n", f"# {CONCEPT_TITLE}s\n"),
            ("concept", f"# {CONCEPT_TITLE}\n", "# Knowledge\n"),
            ("index", "# § Epistemology\n", "# Epistemology\n"),
            ("run", "# Run 2026-04-11\n", "# Run 2026-04-12\n"),
        ],
    )
    def test_h1_title_mismatch(self, tx_notes: TxNoteBuilder, kind: str, old: str, new: str) -> None:
        text = _swap(_note(tx_notes, kind), old, new)

        assert _rules(text, STEMS[kind]) == ["h1-title-mismatch"]

    def test_h1_with_extra_spaces_matches_title(self, tx_notes: TxNoteBuilder) -> None:
        text = _swap(tx_notes.concept(), f"# {CONCEPT_TITLE}\n", f"#   {CONCEPT_TITLE}  \n")

        assert _rules(text) == []


class TestEmptyBody:
    def test_concept_with_only_h1_before_parent_backmatter(self, tx_notes: TxNoteBuilder) -> None:
        text = _swap(tx_notes.concept(), f"\n{BODY_LINE}", "")
        note = parse_note(text, _path(CONCEPT_ID))

        assert re.findall(r"^# ", note.body, flags=re.MULTILINE) == ["# "]
        assert "- parent:: [[notes/tiromex/20260411140000|§ Epistemology]]" in text
        assert _rules(text) == ["empty-body"]

    def test_index_with_only_h1(self, tx_notes: TxNoteBuilder) -> None:
        text = tx_notes.index(members=[])
        for line in ("Notes on what knowledge is.\n", f"{MEMBERS_OPEN}\n", f"{MEMBERS_CLOSE}\n"):
            text = _swap(text, line, "")

        assert _rules(text, INDEX_ID) == ["empty-body"]

    @pytest.mark.parametrize("kind", ["run", "plain"])
    def test_run_and_plain_notes_may_hold_only_h1(self, tx_notes: TxNoteBuilder, kind: str) -> None:
        body = {"run": "Processed one source.\n", "plain": "Buy bread.\n"}[kind]

        assert _rules(_swap(_note(tx_notes, kind), body, ""), STEMS[kind]) == []

    def test_one_body_line_is_enough(self, tx_notes: TxNoteBuilder) -> None:
        text = _swap(tx_notes.concept(), BODY_LINE, "Short.\n")

        assert _rules(text) == []


class TestIdFormat:
    @pytest.mark.parametrize("kind", TIROMEX_KINDS)
    @pytest.mark.parametrize("bad_id", ["2026041114530", "202604111453000", "2026041114530a", "2026a411145300"])
    def test_zettel_id_format_without_created_mismatch(self, tx_notes: TxNoteBuilder, kind: str, bad_id: str) -> None:
        stem = STEMS[kind]
        text = _swap(_note(tx_notes, kind), f"id: {stem}", f"id: {bad_id}")

        assert _rules(text, bad_id) == ["zettel-id-format"]

    @pytest.mark.parametrize("kind", TIROMEX_KINDS)
    @pytest.mark.parametrize("delta", [1, -1])
    def test_id_filename_mismatch(self, tx_notes: TxNoteBuilder, kind: str, delta: int) -> None:
        stem = str(int(STEMS[kind]) + delta)

        assert _rules(_note(tx_notes, kind), stem) == ["id-filename-mismatch"]

    def test_id_filename_mismatch_on_suffixed_stem(self, tx_notes: TxNoteBuilder) -> None:
        assert _rules(tx_notes.concept(), f"{CONCEPT_ID}-copy") == ["id-filename-mismatch"]

    def test_stem_in_subfolder_is_compared_by_name(self, tx_notes: TxNoteBuilder) -> None:
        note = parse_note(tx_notes.concept(), f"notes/tiromex/sub/{CONCEPT_ID}.md")

        assert validate_note(note) == []


def _with_date(text: str, value: str) -> str:
    result, count = re.subn(r"^date: .*$", f"date: {value}", text, count=1, flags=re.MULTILINE)
    assert count == 1
    return result


class TestIdCreated:
    @pytest.mark.parametrize("kind", TIROMEX_KINDS)
    @pytest.mark.parametrize(
        "new_date",
        ["2026-04-11T14:54:00+02:00", "2026-04-12T14:53:00+02:00", "2026-04-11", "2026-04-11T14:53:07+02:00"],
    )
    def test_id_created_mismatch(self, tx_notes: TxNoteBuilder, kind: str, new_date: str) -> None:
        text = _with_date(_note(tx_notes, kind), new_date)

        assert _rules(text, STEMS[kind]) == ["id-created-mismatch"]

    @pytest.mark.parametrize(
        ("zone", "note_id"), [("Europe/Prague", "20260411145300"), ("Asia/Tokyo", "20260411215300")]
    )
    def test_utc_date_matching_local_wall_clock_passes(
        self, tx_notes: TxNoteBuilder, set_zone: Callable[[str], None], zone: str, note_id: str
    ) -> None:
        set_zone(zone)
        text = _with_date(tx_notes.concept(note_id), "2026-04-11T12:53:00+00:00")

        assert _rules(text, note_id) == []

    @pytest.mark.parametrize(
        ("zone", "note_id"), [("America/New_York", "20260411145300"), ("Europe/Prague", "20260411215300")]
    )
    def test_utc_date_not_matching_local_wall_clock_fails(
        self, tx_notes: TxNoteBuilder, set_zone: Callable[[str], None], zone: str, note_id: str
    ) -> None:
        set_zone(zone)
        text = _with_date(tx_notes.concept(note_id), "2026-04-11T12:53:00+00:00")

        assert _rules(text, note_id) == ["id-created-mismatch"]

    @pytest.mark.parametrize("zone", ["Europe/Prague", "America/New_York"])
    def test_id_matching_the_dates_own_offset_passes(
        self, tx_notes: TxNoteBuilder, set_zone: Callable[[str], None], zone: str
    ) -> None:
        set_zone(zone)
        text = _with_date(tx_notes.concept("20260411125300"), "2026-04-11T12:53:00+00:00")

        assert _rules(text, "20260411125300") == []

    @pytest.mark.parametrize("value", ["someday", "2026-04-11 at noon", "[2026]"])
    def test_unreadable_date_skips_the_date_rules(self, tx_notes: TxNoteBuilder, value: str) -> None:
        assert _rules(_with_date(tx_notes.concept(), value)) == []


class TestConceptFields:
    @pytest.mark.parametrize("value", ["article", "wiki", "ai-prompts", "index"])
    def test_type_species(self, tx_notes: TxNoteBuilder, value: str) -> None:
        assert _rules(_swap(tx_notes.concept(), "type: note", f"type: {value}")) == ["type-species"]

    @pytest.mark.parametrize("value", ["wiki-article", "ai-prompt", "definition"])
    def test_type_species_accepts_concept_note_types(self, tx_notes: TxNoteBuilder, value: str) -> None:
        assert _rules(_swap(tx_notes.concept(), "type: note", f"type: {value}")) == []

    @pytest.mark.parametrize("value", ["theses", "Thesis"])
    def test_concept_type_enum(self, tx_notes: TxNoteBuilder, value: str) -> None:
        text = _swap(tx_notes.concept(), "concept-type: thesis", f"concept-type: {value}")

        assert _rules(text) == ["concept-type-enum"]

    @pytest.mark.parametrize(
        ("field", "good", "bad"),
        [
            ("assent", "accepted", "tentatively"),
            ("assent", "unknown", "Accepted"),
            ("lifecycle", "evergreen", "evergreens"),
            ("lifecycle", "literature", "Fleeting"),
        ],
    )
    def test_assent_and_lifecycle_enums(self, tx_notes: TxNoteBuilder, field: str, good: str, bad: str) -> None:
        current = {"assent": "tentative", "lifecycle": "fleeting"}[field]
        text = tx_notes.concept()

        assert _rules(_swap(text, f"{field}: {current}", f"{field}: {good}")) == []
        assert _rules(_swap(text, f"{field}: {current}", f"{field}: {bad}")) == [f"{field}-enum"]

    @pytest.mark.parametrize("field", ["assent", "lifecycle"])
    def test_assent_and_lifecycle_may_be_absent(self, tx_notes: TxNoteBuilder, field: str) -> None:
        text, count = re.subn(rf"^{field}: .*\n", "", tx_notes.concept(), count=1, flags=re.MULTILINE)
        assert count == 1

        assert _rules(text) == []


class TestClaims:
    @pytest.mark.parametrize("claims", ["claims: c1\n", "claims:\n  id: c1\n  statement: x\n"])
    def test_claims_shape(self, tx_notes: TxNoteBuilder, claims: str) -> None:
        assert _rules(_swap(tx_notes.concept(), CLAIMS_BLOCK, claims)) == ["claims-shape"]

    @pytest.mark.parametrize(
        "claims",
        [
            "claims:\n  - id: c1\n",
            'claims:\n  - statement: "x"\n',
            "claims:\n  - c1\n",
            'claims:\n  - id: c1\n    statement: "x"\n  - id: c2\n',
        ],
    )
    def test_claim_shape(self, tx_notes: TxNoteBuilder, claims: str) -> None:
        assert _rules(_swap(tx_notes.concept(), CLAIMS_BLOCK, claims)) == ["claim-shape"]

    @pytest.mark.parametrize("concept_type", ["thesis", "argument", "observation"])
    @pytest.mark.parametrize("claims", ["", "claims: []\n", "claims: null\n", "claims:\n"])
    def test_claims_required(self, tx_notes: TxNoteBuilder, concept_type: str, claims: str) -> None:
        text = tx_notes.concept(concept_type=concept_type, claims=[])
        if claims:
            text = _with_front(text, claims)

        assert _rules(text) == ["claims-required"]

    def test_aporia_no_claims(self, tx_notes: TxNoteBuilder) -> None:
        assert _rules(tx_notes.concept(concept_type="aporia")) == ["aporia-no-claims"]

    @pytest.mark.parametrize("claims", ["", "claims: []\n", "claims: null\n"])
    def test_aporia_without_claims_passes(self, tx_notes: TxNoteBuilder, claims: str) -> None:
        text = tx_notes.concept(concept_type="aporia", claims=[])
        if claims:
            text = _with_front(text, claims)

        assert _rules(text) == []

    @pytest.mark.parametrize("concept_type", ["thesis", "question"])
    @pytest.mark.parametrize("count", [4, 5, 7])
    def test_claims_count_more_than_three(self, tx_notes: TxNoteBuilder, concept_type: str, count: int) -> None:
        rows = [(f"c{n}", f"Claim {n}") for n in range(1, count + 1)]

        assert _rules(tx_notes.concept(concept_type=concept_type, claims=rows)) == ["claims-count"]

    @pytest.mark.parametrize("count", [1, 2, 3])
    def test_one_to_three_claims_pass(self, tx_notes: TxNoteBuilder, count: int) -> None:
        rows = [(f"c{n}", f"Claim {n}") for n in range(1, count + 1)]

        assert _rules(tx_notes.concept(claims=rows)) == []

    @pytest.mark.parametrize("concept_type", ["question", "example"])
    def test_empty_claims_list_on_other_types_gives_claims_count(
        self, tx_notes: TxNoteBuilder, concept_type: str
    ) -> None:
        text = tx_notes.concept(concept_type=concept_type, claims=[])

        assert _rules(text) == []
        assert _rules(_with_front(text, "claims: []\n")) == ["claims-count"]

    def test_empty_claims_list_on_thesis_gives_claims_required_only(self, tx_notes: TxNoteBuilder) -> None:
        text = _with_front(tx_notes.concept(concept_type="thesis", claims=[]), "claims: []\n")

        assert _rules(text) == ["claims-required"]


class TestDoubts:
    @pytest.mark.parametrize("doubts", ["doubts: regress\n", "doubts:\n  mode: regress\n  claim: c1\n"])
    def test_doubts_shape(self, tx_notes: TxNoteBuilder, doubts: str) -> None:
        assert _rules(_with_front(tx_notes.concept(), doubts)) == ["doubts-shape"]

    @pytest.mark.parametrize(
        "doubts",
        [
            'doubts:\n  - claim: c1\n    rationale: "r"\n',
            'doubts:\n  - mode: regress\n    rationale: "r"\n',
            "doubts:\n  - mode: regress\n    claim: c1\n",
            "doubts:\n  - regress\n",
            DOUBT + "  - mode: regress\n    claim: c1\n",
        ],
    )
    def test_doubt_shape(self, tx_notes: TxNoteBuilder, doubts: str) -> None:
        assert _rules(_with_front(tx_notes.concept(), doubts)) == ["doubt-shape"]

    @pytest.mark.parametrize("mode", ["disagreements", "Regress", "circularity"])
    def test_doubt_mode_enum(self, tx_notes: TxNoteBuilder, mode: str) -> None:
        doubts = _swap(DOUBT, "mode: disagreement", f"mode: {mode}")

        assert _rules(_with_front(tx_notes.concept(), doubts)) == ["doubt-mode-enum"]

    @pytest.mark.parametrize("mode", ["disagreement", "regress", "context-relative", "assumption", "circular"])
    def test_every_doubt_mode_without_target_passes(self, tx_notes: TxNoteBuilder, mode: str) -> None:
        doubts = _swap(DOUBT, "mode: disagreement", f"mode: {mode}")

        assert _rules(_with_front(tx_notes.concept(), doubts)) == []

    @pytest.mark.parametrize(
        "target",
        [
            f"    target: {LINK}.md\n",
            "    target:\n      claim: c2\n",
            f"    target:\n      to: {LINK}.md\n",
            "    target: null\n",
        ],
    )
    def test_doubt_target_shape(self, tx_notes: TxNoteBuilder, target: str) -> None:
        assert _rules(_with_front(tx_notes.concept(), DOUBT + target)) == ["doubt-target-shape"]

    def test_disagreement_with_full_target_passes(self, tx_notes: TxNoteBuilder) -> None:
        assert _rules(_with_front(tx_notes.concept(), DOUBT + TARGET)) == []

    def test_target_shape_is_checked_on_disagreement_only(self, tx_notes: TxNoteBuilder) -> None:
        doubts = _swap(DOUBT, "mode: disagreement", "mode: regress") + f"    target: {LINK}.md\n"

        assert _rules(_with_front(tx_notes.concept(), doubts)) == []


class TestLinkShape:
    @pytest.mark.parametrize(
        "line",
        [
            "- supports:: plain text",
            f"- supports:: [[{LINK}]]",
            f"- supports:: [[{LINK}|]]",
            f"- supports:: [[{LINK}| ]]",
            f"- supports:: [[{LINK}.md|Belief needs grounds]]",
            f"- supports:: [[{LINK}#Part|Belief needs grounds]]",
            f"- requires:: [[{LINK}|Belief needs grounds]], [[notes/tiromex/20260413100000]]",
        ],
    )
    def test_bad_relation_value(self, tx_notes: TxNoteBuilder, line: str) -> None:
        assert _rules(tx_notes.concept(backmatter=[line])) == ["link-shape"]

    @pytest.mark.parametrize("title", ["", " "])
    def test_parent_with_blank_title(self, tx_notes: TxNoteBuilder, title: str) -> None:
        assert _rules(tx_notes.concept(parent_title=title)) == ["link-shape"]

    @pytest.mark.parametrize("value", ["Epistemology", "[[notes/tiromex/20260411130000|]]"])
    def test_bad_parent_on_index(self, tx_notes: TxNoteBuilder, value: str) -> None:
        text = tx_notes.index() + f"\n---\n\n- parent:: {value}\n"

        assert _rules(text, INDEX_ID) == ["link-shape"]

    @pytest.mark.parametrize(
        "line",
        [
            f"- supports:: [[{LINK}|Belief.md]]",
            f"- supports:: [[{LINK}|C# basics]]",
            f"- analogous-to:: [[{LINK}|Belief]], [[notes/tiromex/sub/20260413100000|Grounds]]",
        ],
    )
    def test_good_relation_value_passes(self, tx_notes: TxNoteBuilder, line: str) -> None:
        assert _rules(tx_notes.concept(backmatter=[line])) == []

    def test_index_with_good_parent_passes(self, tx_notes: TxNoteBuilder) -> None:
        text = tx_notes.index() + "\n---\n\n- parent:: [[notes/tiromex/20260411130000|§ Philosophy]]\n"

        assert _rules(text, INDEX_ID) == []


class TestSourceShape:
    @pytest.mark.parametrize(
        "value",
        [
            "books/plato/republic.pdf",
            "MIRROR:books/republic.pdf",
            "mirror:books",
            "mirror:books//etc/passwd",
            "mirror:books/../secret.pdf",
            "mirror:books/plato/../../secret.pdf",
            "mirror:books/republic.pdf, mirror:papers",
            "mirror:/republic.pdf",
            "mirror:books/",
        ],
    )
    def test_bad_source(self, tx_notes: TxNoteBuilder, value: str) -> None:
        assert _rules(tx_notes.concept(backmatter=[f"- source:: {value}"])) == ["source-shape"]

    @pytest.mark.parametrize(
        "value",
        [
            "mirror:books/plato/republic.pdf",
            "mirror:books/a..b.pdf",
            "mirror:books/republic.pdf, mirror:papers/gettier.pdf",
        ],
    )
    def test_good_source_passes(self, tx_notes: TxNoteBuilder, value: str) -> None:
        assert _rules(tx_notes.concept(backmatter=[f"- source:: {value}"])) == []

    def test_index_source_is_not_checked(self, tx_notes: TxNoteBuilder) -> None:
        text = tx_notes.index() + "\n---\n\n- source:: books/plato.pdf\n"

        assert _rules(text, INDEX_ID) == []


class TestStructure:
    def test_orphan_concept(self, tx_notes: TxNoteBuilder) -> None:
        text = _swap(
            tx_notes.concept(),
            "- parent:: [[notes/tiromex/20260411140000|§ Epistemology]]",
            f"- supports:: [[{LINK}|Belief needs grounds]]",
        )

        assert _rules(text) == ["orphan-concept"]

    @pytest.mark.parametrize(("kind", "lines"), [("concept", 2), ("index", 5)])
    def test_oversized_body_follows_max_body_lines(self, tx_notes: TxNoteBuilder, kind: str, lines: int) -> None:
        text = _note(tx_notes, kind)

        assert _rules(text, STEMS[kind], max_body_lines=lines) == []
        assert _rules(text, STEMS[kind], max_body_lines=lines - 1) == ["oversized-body"]

    @pytest.mark.parametrize(("extra", "expected"), [(58, []), (59, ["oversized-body"])])
    def test_oversized_body_default_is_sixty_lines(
        self, tx_notes: TxNoteBuilder, extra: int, expected: list[str]
    ) -> None:
        added = "".join(f"Line {n}.\n" for n in range(extra))

        assert _rules(_swap(tx_notes.concept(), BODY_LINE, BODY_LINE + added)) == expected

    @pytest.mark.parametrize("kind", ["run", "plain"])
    def test_run_and_plain_notes_have_no_size_limit(self, tx_notes: TxNoteBuilder, kind: str) -> None:
        assert _rules(_note(tx_notes, kind), STEMS[kind], max_body_lines=1) == []

    @pytest.mark.parametrize("kind", ["concept", "index"])
    @pytest.mark.parametrize(
        ("reviewed", "updated"),
        [
            ("2026-04-01T10:00:00+02:00", "2026-04-02T10:00:00+02:00"),
            ("2026-04-01", "2026-04-01T10:00:00+02:00"),
            # reviewed is 2026-04-01T23:00Z, updated is 2026-04-02T01:00Z: older instant, later string
            ("2026-04-02T01:00:00+02:00", "2026-04-01T20:00:00-05:00"),
        ],
    )
    def test_stale_review(self, tx_notes: TxNoteBuilder, kind: str, reviewed: str, updated: str) -> None:
        text = _with_front(_note(tx_notes, kind), f"reviewed: {reviewed}\nupdated: {updated}\n")

        assert _rules(text, STEMS[kind]) == ["stale-review"]

    @pytest.mark.parametrize(
        "extra",
        [
            "reviewed: 2026-04-02T10:00:00+02:00\nupdated: 2026-04-01T10:00:00+02:00\n",
            "reviewed: 2026-04-01T10:00:00+02:00\nupdated: 2026-04-01T10:00:00+02:00\n",
            "reviewed: 2026-04-01T10:00:00+02:00\n",
            "reviewed: soon\nupdated: 2026-04-02T10:00:00+02:00\n",
            # reviewed is 2026-04-02T01:00Z, updated is 2026-04-01T23:00Z: later instant, earlier string
            "reviewed: 2026-04-01T20:00:00-05:00\nupdated: 2026-04-02T01:00:00+02:00\n",
        ],
    )
    def test_fresh_or_unreadable_review_passes(self, tx_notes: TxNoteBuilder, extra: str) -> None:
        assert _rules(_with_front(tx_notes.concept(), extra)) == []

    def test_run_note_has_no_stale_review_rule(self, tx_notes: TxNoteBuilder) -> None:
        text = _with_front(tx_notes.run(), "reviewed: 2026-04-01\nupdated: 2026-04-02T10:00:00+02:00\n")

        assert _rules(text, RUN_ID) == []


class TestIndexRules:
    @pytest.mark.parametrize("title", ["Epistemology", "§Epistemology", "Epistemology §"])
    def test_index_title(self, tx_notes: TxNoteBuilder, title: str) -> None:
        assert _rules(tx_notes.index(title=title), INDEX_ID) == ["index-title"]

    def test_index_title_with_section_sign_passes(self, tx_notes: TxNoteBuilder) -> None:
        assert _rules(tx_notes.index(title="§ Ethics"), INDEX_ID) == []

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            (f"{MEMBERS_OPEN}\n", f"{MEMBERS_OPEN}\n{MEMBERS_OPEN}\n"),
            (f"{MEMBERS_CLOSE}\n", f"{MEMBERS_CLOSE}\n{MEMBERS_CLOSE}\n"),
            (f"{MEMBERS_OPEN}\n", ""),
            (f"{MEMBERS_CLOSE}\n", ""),
            (f"{MEMBERS_CLOSE}\n", f"{MEMBERS_CLOSE}\n{MEMBERS_OPEN}\n- more\n{MEMBERS_CLOSE}\n"),
        ],
    )
    def test_members_block(self, tx_notes: TxNoteBuilder, old: str, new: str) -> None:
        assert _rules(_swap(tx_notes.index(), old, new), INDEX_ID) == ["members-block"]

    def test_members_block_close_before_open(self, tx_notes: TxNoteBuilder) -> None:
        text = _swap(tx_notes.index(), MEMBERS_OPEN, "@@OPEN@@")
        text = _swap(_swap(text, MEMBERS_CLOSE, MEMBERS_OPEN), "@@OPEN@@", MEMBERS_CLOSE)

        assert _rules(text, INDEX_ID) == ["members-block"]

    @pytest.mark.parametrize("members", [[], [("20260411145300", "A"), ("20260412090000", "B")]])
    def test_members_block_absent_or_well_formed_passes(
        self, tx_notes: TxNoteBuilder, members: list[tuple[str, str]]
    ) -> None:
        text = tx_notes.index(members=members)
        bare = _swap(_swap(text, f"{MEMBERS_OPEN}\n", ""), f"{MEMBERS_CLOSE}\n", "")

        assert _rules(text, INDEX_ID) == []
        assert _rules(bare, INDEX_ID) == []


class TestOddValues:
    @pytest.mark.parametrize("kind", ["concept", "run"])
    def test_numeric_title_does_not_crash(self, tx_notes: TxNoteBuilder, kind: str) -> None:
        text = _note(tx_notes, kind)
        title = {"concept": CONCEPT_TITLE, "run": "Run 2026-04-11"}[kind]
        text = _swap(_swap(text, f'title: "{title}"', "title: 2026"), f"# {title}\n", "# 2026\n")

        assert _rules(text, STEMS[kind]) == []

    @pytest.mark.parametrize(("tags", "expected"), [("[2026, knowledge]", []), ("[2026, book]", ["forbidden-tag"])])
    def test_non_string_tag_does_not_crash(self, tx_notes: TxNoteBuilder, tags: str, expected: list[str]) -> None:
        text = _swap(tx_notes.concept(), "tags: []", f"tags: {tags}")

        assert _rules(text) == expected
