"""Rule discovery, host-file rendering and the relaxed source layout (PRD 00116)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from braid.domain import engine
from braid.domain.model import BraidError, Result, is_legacy_skills_source
from braid.domain.rules import (
    DIRECTORY_HOSTS,
    GENERATED_HEADER,
    GENERATED_LIMIT,
    HOST_INSTRUCTION_PATHS,
    KNOWN_HOSTS,
    SINGLE_FILE_HOSTS,
    RuleInventory,
    RuleState,
    discover_rules,
    render_host_file,
)

from tests.tools.braid.helpers import make_host_rule, make_rule, make_skill, settings

NOT_UTF8 = b"\xff\xfe\x00not utf-8"


# --- source layout -------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["rules", "hosts"])
def test_layout_accepts_a_source_without_skills_and_links_no_skill_from_it(tmp_path: Path, kind: str) -> None:
    skills = tmp_path / "personal"
    make_skill(skills, "portable")
    rule_only = tmp_path / "rule-only"
    if kind == "rules":
        make_rule(rule_only, "portable")
    else:
        make_host_rule(rule_only, "codex", "portable")
    config = settings(tmp_path, skills, rule_only)

    engine.discover_inventory([rule_only])
    engine.run(config)

    for root in (config.agents_root, config.claude_root):
        linked = sorted(path.name for path in (root / "skills").iterdir())
        assert linked == ["portable"]
        assert (root / "skills" / "portable").resolve() == (skills / "skills" / "portable").resolve()


@pytest.mark.parametrize(
    "entries",
    [(), ("rule",), ("skill", "host"), ("hosts-old", "rules.bak")],
    ids=["empty", "singular-rule", "singular-skill-host", "near-miss-names"],
)
def test_layout_refuses_a_source_with_no_skills_rules_or_hosts_directory(
    tmp_path: Path, entries: tuple[str, ...]
) -> None:
    source = tmp_path / "bare"
    source.mkdir()
    for name in entries:
        (source / name).mkdir()

    with pytest.raises(BraidError) as raised:
        engine.discover_inventory([Path("bare")])

    assert str(raised.value) == f"source has no skills, rules or hosts directory: {source}"


def test_layout_refuses_rules_and_hosts_that_are_files_not_directories(tmp_path: Path) -> None:
    source = tmp_path / "files"
    source.mkdir()
    (source / "rules").write_text("not a directory")
    (source / "hosts").write_text("not a directory")
    make_skill(tmp_path / "personal", "portable")

    with pytest.raises(BraidError) as raised:
        engine.run(settings(tmp_path, tmp_path / "personal", source))

    assert str(raised.value) == f"source has no skills, rules or hosts directory: {source}"


def policy_files_for(tmp_path: Path, source: Path) -> tuple[Path, ...]:
    config_root = tmp_path / "config"
    config_root.mkdir(exist_ok=True)
    request = engine.ComposeRequest(
        agents_root=tmp_path / "home" / ".agents",
        claude_root=tmp_path / "home" / ".claude",
        config_root=config_root,
        sources=(source,),
    )
    return tuple(engine.resolve_settings(request).policy_files)


@pytest.mark.parametrize("kind", ["rules", "hosts"])
def test_layout_loads_the_policy_of_a_source_without_skills_from_the_source_itself(tmp_path: Path, kind: str) -> None:
    parent = tmp_path / "repo"
    source = parent / "rule-only"
    if kind == "rules":
        make_rule(source, "tone")
    else:
        make_host_rule(source, "codex", "tone")
    (source / ".braidignore").write_text("tone\n")
    (parent / ".braidignore").write_text("portable\n")

    policy_files = policy_files_for(tmp_path, source)

    assert [Path(path).resolve() for path in policy_files] == [(source / ".braidignore").resolve()]


def test_layout_loads_the_policy_of_a_legacy_skills_source_from_its_parent(tmp_path: Path) -> None:
    parent = tmp_path / "old"
    make_skill(parent, "portable")
    legacy = parent / "skills"
    (parent / ".braidignore").write_text("portable\n")
    (legacy / ".braidignore").write_text("other\n")

    policy_files = policy_files_for(tmp_path, legacy)

    assert [Path(path).resolve() for path in policy_files] == [(parent / ".braidignore").resolve()]


def test_layout_recognises_only_a_configured_skills_directory_as_legacy(tmp_path: Path) -> None:
    legacy = tmp_path / "old" / "skills"
    legacy.mkdir(parents=True)
    nested = tmp_path / "personal"
    (nested / "skills").mkdir(parents=True)
    wrapped = tmp_path / "wrapped" / "skills"
    (wrapped / "skills").mkdir(parents=True)
    near_miss = tmp_path / "skills-old"
    near_miss.mkdir()

    assert is_legacy_skills_source(legacy) is True
    assert is_legacy_skills_source(nested) is False
    assert is_legacy_skills_source(wrapped) is False
    assert is_legacy_skills_source(near_miss) is False
    assert is_legacy_skills_source(tmp_path / "missing" / "skills") is False


def test_layout_result_counts_generated_and_unmanaged_from_zero() -> None:
    assert Result().generated == 0
    assert Result().unmanaged == 0
    assert Result(generated=2, unmanaged=3).generated == 2
    assert Result(generated=2, unmanaged=3).unmanaged == 3


def test_layout_host_constants_match_the_contract() -> None:
    assert KNOWN_HOSTS == ("claude", "kiro", "codex", "copilot", "pi", "gemini")
    assert SINGLE_FILE_HOSTS == ("codex", "copilot", "pi", "gemini")
    assert DIRECTORY_HOSTS == ("claude", "kiro")
    assert HOST_INSTRUCTION_PATHS == {
        "codex": Path(".codex") / "AGENTS.md",
        "copilot": Path(".copilot") / "copilot-instructions.md",
        "pi": Path(".pi") / "agent" / "AGENTS.md",
        "gemini": Path(".gemini") / "GEMINI.md",
    }
    assert GENERATED_HEADER == "<!-- Generated by braid. Edit the rule sources, not this file. -->"
    assert GENERATED_LIMIT == 32768


# --- discover_rules ------------------------------------------------------------------------


def test_discover_orders_shared_rules_by_source_position_then_name(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    zeta = make_rule(first, "zeta")
    alpha = make_rule(first, "alpha")
    beta = make_rule(second, "beta")
    aardvark = make_rule(second, "aardvark")

    inventory = discover_rules([second, first])

    assert list(inventory.shared.items()) == [
        ("aardvark", aardvark.resolve()),
        ("beta", beta.resolve()),
        ("alpha", alpha.resolve()),
        ("zeta", zeta.resolve()),
    ]
    assert inventory.hosts == {}
    assert inventory.empty is False


def test_discover_collects_host_rules_only_for_hosts_that_have_rules(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    shared = make_rule(source, "tone")
    codex_b = make_host_rule(source, "codex", "b-codex")
    codex_a = make_host_rule(source, "codex", "a-codex")
    kiro = make_host_rule(source, "kiro", "steer")
    (source / "hosts" / "claude").mkdir()
    (source / "hosts" / "gemini" / "rules").mkdir(parents=True)

    inventory = discover_rules([source])

    assert inventory.shared == {"tone": shared.resolve()}
    assert set(inventory.hosts) == {"codex", "kiro"}
    assert list(inventory.hosts["codex"].items()) == [
        ("a-codex", codex_a.resolve()),
        ("b-codex", codex_b.resolve()),
    ]
    assert inventory.hosts["kiro"] == {"steer": kiro.resolve()}


def test_discover_reports_an_empty_inventory_for_no_rules(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    (source / "rules").mkdir(parents=True)
    host_only = tmp_path / "host-only"
    make_host_rule(host_only, "pi", "terse")

    assert discover_rules([]).empty is True
    assert discover_rules([source]) == RuleInventory(shared={}, hosts={})
    assert discover_rules([source]).empty is True
    assert discover_rules([host_only]).empty is False


def test_discover_skips_symlinked_dotted_plain_and_markerless_rule_entries(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    kept = make_rule(source, "kept")
    elsewhere = make_rule(tmp_path / "elsewhere", "linked")
    rules = source / "rules"
    (rules / "linked").symlink_to(elsewhere, target_is_directory=True)
    (rules / ".hidden").mkdir()
    (rules / ".hidden" / "RULE.md").write_bytes(NOT_UTF8)
    (rules / "plain-file").write_text("not a rule directory")
    (rules / "No_Marker").mkdir()
    (rules / "No_Marker" / "README.md").write_text("no RULE.md here")
    (rules / "marker-dir").mkdir()
    (rules / "marker-dir" / "RULE.md").mkdir()

    inventory = discover_rules([source])

    assert inventory.shared == {"kept": kept.resolve()}


def test_discover_skips_symlinked_dotted_and_plain_host_entries(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    kept = make_host_rule(source, "codex", "kept")
    hosts = source / "hosts"
    linked = make_host_rule(tmp_path / "elsewhere", "kiro", "linked")
    (hosts / "kiro").symlink_to(tmp_path / "elsewhere" / "hosts" / "kiro", target_is_directory=True)
    (hosts / ".vscode").mkdir()
    (hosts / "notes.md").write_text("not a host directory")
    (hosts / "codex" / "rules" / "linked").symlink_to(linked, target_is_directory=True)

    inventory = discover_rules([source])

    assert inventory.hosts == {"codex": {"kept": kept.resolve()}}


def test_discover_ignores_rules_inside_a_configured_legacy_skills_directory(tmp_path: Path) -> None:
    legacy = tmp_path / "old" / "skills"
    make_rule(legacy, "hidden-rule")
    nested = tmp_path / "personal"
    make_skill(nested, "portable")
    shown = make_rule(nested, "shown-rule")

    inventory = discover_rules([legacy, nested])

    assert inventory.shared == {"shown-rule": shown.resolve()}


def test_discover_skips_a_source_already_seen_through_an_alias(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    tone = make_rule(source, "tone")
    host = make_host_rule(source, "copilot", "terse")
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)

    inventory = discover_rules([alias, source, alias])

    assert inventory.shared == {"tone": tone.resolve()}
    assert inventory.hosts == {"copilot": {"terse": host.resolve()}}


@pytest.mark.parametrize("name", ["Tone", "tone_style", "tone.md", "tone style"])
def test_discover_refuses_an_invalid_shared_rule_name(tmp_path: Path, name: str) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone-2")
    bad = make_rule(source, name)

    with pytest.raises(BraidError) as raised:
        discover_rules([source])

    assert str(raised.value) == f"invalid rule name {name!r}: {bad}"


def test_discover_refuses_an_invalid_host_rule_name(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_host_rule(source, "gemini", "fine-1")
    bad = make_host_rule(source, "gemini", "Bad_Name")

    with pytest.raises(BraidError) as raised:
        discover_rules([source])

    assert str(raised.value) == f"invalid rule name 'Bad_Name': {bad}"


@pytest.mark.parametrize("name", ["vscode", "claude-code", "codexx", "Kiro"])
def test_discover_refuses_an_unknown_host_directory(tmp_path: Path, name: str) -> None:
    source = tmp_path / "personal"
    make_host_rule(source, "claude", "tone")
    (source / "hosts" / name).mkdir()

    with pytest.raises(BraidError) as raised:
        discover_rules([source])

    assert str(raised.value) == f"unknown host directory: {source / 'hosts' / name}"


@pytest.mark.parametrize("host", KNOWN_HOSTS)
def test_discover_accepts_every_known_host_directory(tmp_path: Path, host: str) -> None:
    source = tmp_path / "personal"
    rule = make_host_rule(source, host, "tone")

    assert discover_rules([source]).hosts == {host: {"tone": rule.resolve()}}


def test_discover_refuses_a_non_utf8_rule(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "fine")
    broken = make_host_rule(source, "pi", "broken")
    (broken / "RULE.md").write_bytes(NOT_UTF8)

    with pytest.raises(BraidError, match=re.escape(f"cannot read {broken / 'RULE.md'}: ")):
        discover_rules([source])


# --- duplicates ----------------------------------------------------------------------------


def duplicate_message(name: str, first: Path, configured: Path) -> str:
    return f"duplicate rule name {name!r}: {first} and {configured}"


def test_duplicate_shared_rule_across_sources_is_refused(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_rule(first, "tone")
    make_rule(first, "other")
    make_rule(second, "tone")

    with pytest.raises(BraidError) as raised:
        discover_rules([Path("first"), second])

    assert str(raised.value) == duplicate_message("tone", first, second)


def test_duplicate_host_rule_shadowing_a_shared_rule_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone")
    make_host_rule(source, "codex", "tone")

    with pytest.raises(BraidError) as raised:
        discover_rules([source])

    assert str(raised.value) == duplicate_message("tone", source, source)


def test_duplicate_shared_rule_found_after_a_host_rule_is_refused(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_host_rule(first, "kiro", "tone")
    make_rule(second, "tone")

    with pytest.raises(BraidError) as raised:
        discover_rules([first, second])

    assert str(raised.value) == duplicate_message("tone", first, second)


def test_duplicate_rule_for_the_same_host_is_refused(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_host_rule(first, "copilot", "terse")
    make_host_rule(second, "copilot", "terse")

    with pytest.raises(BraidError) as raised:
        discover_rules([first, second])

    assert str(raised.value) == duplicate_message("terse", first, second)


def test_duplicate_name_check_allows_one_name_on_two_hosts_and_as_a_skill(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_skill(first, "terse")
    codex = make_host_rule(first, "codex", "terse")
    copilot = make_host_rule(second, "copilot", "terse")

    inventory = discover_rules([first, second])

    assert inventory.shared == {}
    assert inventory.hosts == {"codex": {"terse": codex.resolve()}, "copilot": {"terse": copilot.resolve()}}


# --- render_host_file ----------------------------------------------------------------------


def test_render_joins_shared_then_host_bodies_in_mapping_order(tmp_path: Path) -> None:
    zeta = make_rule(tmp_path / "a", "zeta", "# Zeta\n\nAlways zeta.\n\n\n")
    alpha = make_rule(tmp_path / "a", "alpha", "# Alpha  \t\n")
    host_y = make_host_rule(tmp_path / "a", "codex", "y-host", "\n# Y host\nline two")
    host_b = make_host_rule(tmp_path / "a", "codex", "b-host", "# B host\n")

    rendered = render_host_file({"zeta": zeta, "alpha": alpha}, {"y-host": host_y, "b-host": host_b})

    assert rendered == (
        "<!-- Generated by braid. Edit the rule sources, not this file. -->\n"
        "\n"
        "# Zeta\n\nAlways zeta.\n"
        "\n"
        "# Alpha\n"
        "\n"
        "\n# Y host\nline two\n"
        "\n"
        "# B host\n"
    )


def test_render_drops_empty_bodies(tmp_path: Path) -> None:
    blank = make_rule(tmp_path / "a", "blank", " \n\t\n")
    empty = make_rule(tmp_path / "a", "empty", "")
    kept = make_host_rule(tmp_path / "a", "pi", "kept", "Kept body.")

    rendered = render_host_file({"blank": blank, "empty": empty}, {"kept": kept})

    assert rendered == f"{GENERATED_HEADER}\n\nKept body.\n"


def test_render_with_no_rules_is_the_header_line_alone() -> None:
    assert render_host_file({}, {}) == GENERATED_HEADER + "\n"


def test_render_of_discovered_rules_follows_inventory_order(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_rule(second, "b-shared", "Second source.")
    make_rule(first, "z-shared", "First source.")
    make_host_rule(first, "gemini", "only-gemini", "Gemini only.")
    make_host_rule(first, "codex", "only-codex", "Codex only.")

    inventory = discover_rules([first, second])
    rendered = render_host_file(inventory.shared, inventory.hosts["gemini"])

    assert rendered == f"{GENERATED_HEADER}\n\nFirst source.\n\nSecond source.\n\nGemini only.\n"


def test_render_refuses_an_unreadable_rule(tmp_path: Path) -> None:
    broken = make_rule(tmp_path / "a", "broken")
    (broken / "RULE.md").write_bytes(NOT_UTF8)
    missing = tmp_path / "a" / "rules" / "missing"
    missing.mkdir()

    with pytest.raises(BraidError, match=re.escape(f"cannot read {broken / 'RULE.md'}: ")):
        render_host_file({"broken": broken}, {})
    with pytest.raises(BraidError, match=re.escape(f"cannot read {missing / 'RULE.md'}: ")):
        render_host_file({}, {"missing": missing})


# --- RuleState -----------------------------------------------------------------------------


def full_state_payload() -> dict[str, object]:
    return {
        "union": {"tone": "/src/a/rules/tone", "terse": "/src/b/rules/terse"},
        "hosts": {"codex": {"only-codex": "/src/a/hosts/codex/rules/only-codex"}},
        "projected": {"claude": {"tone": "/home/.agents/rules/tone/RULE.md"}},
        "generated": {"codex": "/home/.agents/hosts/codex/AGENTS.md", "pi": "/home/.agents/hosts/pi/AGENTS.md"},
        "instructions": {"codex": "/home/.codex/AGENTS.md"},
    }


def test_layout_of_an_empty_rule_state_holds_all_five_keys(tmp_path: Path) -> None:
    empty = RuleState.empty()

    assert empty.as_json() == {"union": {}, "hosts": {}, "projected": {}, "generated": {}, "instructions": {}}
    assert RuleState.from_json(empty.as_json(), tmp_path / "state.json") == empty


def test_layout_of_a_rule_state_survives_a_json_round_trip(tmp_path: Path) -> None:
    payload = full_state_payload()

    state = RuleState.from_json(json.loads(json.dumps(payload)), tmp_path / "state.json")

    assert state.as_json() == payload
    assert state.union == {"tone": "/src/a/rules/tone", "terse": "/src/b/rules/terse"}
    assert state.instructions == {"codex": "/home/.codex/AGENTS.md"}
    assert state != RuleState.empty()


def corrupt(key: str, value: object) -> dict[str, object]:
    payload = full_state_payload()
    payload[key] = value
    return payload


def missing(key: str) -> dict[str, object]:
    payload = full_state_payload()
    del payload[key]
    return payload


@pytest.mark.parametrize(
    "payload",
    [
        [],
        None,
        missing("instructions"),
        missing("union"),
        corrupt("union", ["tone"]),
        corrupt("union", {"tone": 1}),
        corrupt("generated", {"codex": None}),
        corrupt("hosts", {"codex": "/src/a"}),
        corrupt("hosts", {"codex": {"tone": 1}}),
        corrupt("hosts", {"vscode": {}}),
        corrupt("projected", {"codex": {}}),
        corrupt("projected", {"claude": {"tone": ["x"]}}),
        corrupt("generated", {"claude": "/home/.agents/hosts/claude/AGENTS.md"}),
        corrupt("instructions", {"kiro": "/home/.kiro/AGENTS.md"}),
    ],
    ids=[
        "list",
        "null",
        "no-instructions",
        "no-union",
        "union-list",
        "union-int-value",
        "generated-null-value",
        "hosts-flat",
        "hosts-int-value",
        "hosts-unknown_host",
        "projected-single-file-host",
        "projected-list-value",
        "generated-directory-host",
        "instructions-directory-host",
    ],
)
def test_layout_of_a_corrupt_rule_state_is_refused(tmp_path: Path, payload: object) -> None:
    state_path = tmp_path / "home" / ".agents" / ".braid-state.json"

    with pytest.raises(BraidError) as raised:
        RuleState.from_json(payload, state_path)

    assert str(raised.value) == f"invalid rules state in {state_path}"
