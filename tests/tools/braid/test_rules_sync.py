"""sync_rules: rule projections, generated host files, instruction links and rules state (PRD 00116)."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from braid.domain.engine import BraidError, Mode, Settings, run
from braid.domain.model import Result
from braid.domain.rules import (
    GENERATED_HEADER,
    GENERATED_LIMIT,
    HOST_INSTRUCTION_PATHS,
    SINGLE_FILE_HOSTS,
    RuleState,
    discover_rules,
    render_host_file,
    sync_rules,
)

from tests.tools.braid.helpers import (
    deny_file_symlinks,
    enroll,
    generated_file,
    kiro_root,
    make_host_roots,
    make_host_rule,
    make_rule,
    make_skill,
    read_state,
    settings,
    write_policy,
)


def instruction_link(config: Settings, host: str) -> Path:
    return config.agents_root.parent / HOST_INSTRUCTION_PATHS[host]


# --- exit criteria -------------------------------------------------------------------------


def sync_exit_scenario(tmp_path: Path) -> tuple[Settings, dict[str, Path]]:
    first = tmp_path / "first"
    second = tmp_path / "second"
    rules = {
        "safety": make_rule(first, "safety", "Be safe.").resolve(),
        "claude-only": make_host_rule(first, "claude", "claude-only", "Claude only.").resolve(),
        "codex-only": make_host_rule(second, "codex", "codex-only", "Codex only.").resolve(),
    }
    config = enroll(settings(tmp_path, first, second))
    make_host_roots(config, *SINGLE_FILE_HOSTS)
    run(config)
    return config, rules


def test_exit_criteria_sync_creates_every_rule_link_and_generated_file(tmp_path: Path) -> None:
    config, rules = sync_exit_scenario(tmp_path)
    agents = config.agents_root

    assert (agents / "rules" / "safety").is_symlink()
    assert (agents / "rules" / "safety").resolve() == rules["safety"]
    assert (agents / "hosts" / "claude" / "rules" / "claude-only").resolve() == rules["claude-only"]
    assert (agents / "hosts" / "codex" / "rules" / "codex-only").resolve() == rules["codex-only"]
    assert sorted(path.name for path in (config.claude_root / "rules").iterdir()) == ["claude-only.md", "safety.md"]
    assert sorted(path.name for path in (kiro_root(config) / "steering").iterdir()) == ["safety.md"]
    for link, rule in (
        (config.claude_root / "rules" / "safety.md", "safety"),
        (config.claude_root / "rules" / "claude-only.md", "claude-only"),
        (kiro_root(config) / "steering" / "safety.md", "safety"),
    ):
        assert link.is_symlink() and link.resolve() == rules[rule] / "RULE.md"
    for host in SINGLE_FILE_HOSTS:
        link = instruction_link(config, host)
        assert link.is_symlink() and link.resolve() == generated_file(config, host).resolve()
    codex = generated_file(config, "codex").read_text()
    copilot = generated_file(config, "copilot").read_text()
    assert "Be safe." in codex and "Codex only." in codex and "Claude only." not in codex
    assert "Be safe." in copilot and "Codex only." not in copilot


def test_exit_criteria_state_records_every_projection_and_check_is_clean(tmp_path: Path) -> None:
    config, rules = sync_exit_scenario(tmp_path)
    agents = config.agents_root
    reported: list[str] = []

    result = run(config.with_mode(Mode.CHECK), emit=reported.append)

    shared_file = str(agents / "rules" / "safety" / "RULE.md")
    assert read_state(config)["rules"] == {
        "union": {"safety": str(rules["safety"])},
        "hosts": {
            "claude": {"claude-only": str(rules["claude-only"])},
            "codex": {"codex-only": str(rules["codex-only"])},
        },
        "projected": {
            "claude": {
                "safety": shared_file,
                "claude-only": str(agents / "hosts" / "claude" / "rules" / "claude-only" / "RULE.md"),
            },
            "kiro": {"safety": shared_file},
        },
        "generated": {host: str(generated_file(config, host)) for host in SINGLE_FILE_HOSTS},
        "instructions": {host: str(instruction_link(config, host)) for host in SINGLE_FILE_HOSTS},
    }
    assert reported == []
    assert result.drift == 0


# --- generated files -----------------------------------------------------------------------


def test_generated_file_holds_header_then_shared_then_host_bodies_in_source_order(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_rule(second, "b-shared", "Second shared.\n\n\n")
    make_rule(first, "z-shared", "First z.")
    make_rule(first, "a-shared", "First a.")
    make_host_rule(second, "codex", "a-codex", "Codex second.")
    make_host_rule(first, "codex", "z-codex", "Codex first.\n")
    make_host_rule(first, "pi", "pi-only", "Pi only.")
    config = settings(tmp_path, first, second)

    run(config)

    shared = f"{GENERATED_HEADER}\n\nFirst a.\n\nFirst z.\n\nSecond shared.\n"
    assert generated_file(config, "codex").read_bytes() == f"{shared}\nCodex first.\n\nCodex second.\n".encode()
    assert generated_file(config, "copilot").read_bytes() == shared.encode()
    assert generated_file(config, "pi").read_bytes() == f"{shared}\nPi only.\n".encode()
    inventory = discover_rules([first, second])
    for host in SINGLE_FILE_HOSTS:
        expected = render_host_file(inventory.shared, inventory.hosts.get(host, {})).encode("utf-8")
        assert generated_file(config, host).read_bytes() == expected


def test_removing_every_rule_leaves_header_only_generated_files(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    tone = make_rule(source, "tone", "Tone.")
    config = settings(tmp_path, source)
    make_host_roots(config, "codex")
    run(config)
    shutil.rmtree(tone)

    run(config)

    for host in SINGLE_FILE_HOSTS:
        assert generated_file(config, host).read_text() == f"{GENERATED_HEADER}\n"
    assert instruction_link(config, "codex").read_text() == f"{GENERATED_HEADER}\n"
    rules = read_state(config)["rules"]
    assert rules["union"] == {}
    assert set(rules["generated"]) == set(SINGLE_FILE_HOSTS)
    assert rules["instructions"] == {"codex": str(instruction_link(config, "codex"))}
    assert not os.path.lexists(config.claude_root / "rules" / "tone.md")
    assert run(config.with_mode(Mode.CHECK)).drift == 0


def test_unrecorded_generated_file_is_backed_up_before_the_first_generate(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone", "Tone.")
    config = settings(tmp_path, source)
    path = generated_file(config, "codex")
    path.parent.mkdir(parents=True)
    path.write_text("hand written\n")
    emitted: list[str] = []

    run(config, emit=emitted.append)

    backups = list((config.agents_root / "backups").glob("*/generated/codex/*"))
    assert [backup.read_text() for backup in backups] == ["hand written\n"]
    assert list((config.agents_root / "backups").glob("*/generated/copilot/*")) == []
    backup_line = next(i for i, line in enumerate(emitted) if line.startswith("BACKUP ") and str(path) in line)
    assert backup_line < emitted.index(f"GENERATE {path}")
    assert path.read_text() == f"{GENERATED_HEADER}\n\nTone.\n"


def test_edited_recorded_generated_file_is_overwritten_without_backup(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone", "Tone.")
    config = settings(tmp_path, source)
    run(config)
    path = generated_file(config, "codex")
    path.write_text("edited by hand\n")
    emitted: list[str] = []

    result = run(config, emit=emitted.append)

    assert emitted == [f"GENERATE {path}"]
    assert result.generated == 1
    assert path.read_text() == f"{GENERATED_HEADER}\n\nTone.\n"
    assert not (config.agents_root / "backups").exists()


def test_same_length_edit_of_a_generated_file_is_drift_and_is_regenerated(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone", "Tone.")
    config = settings(tmp_path, source)
    run(config)
    path = generated_file(config, "codex")
    expected = path.read_bytes()
    edited = expected.replace(b"Tone.", b"Tonx.")
    assert len(edited) == len(expected) and edited != expected
    path.write_bytes(edited)
    reported: list[str] = []
    emitted: list[str] = []

    check = run(config.with_mode(Mode.CHECK), emit=reported.append)
    assert path.read_bytes() == edited
    result = run(config, emit=emitted.append)

    assert reported == [f"MISMATCH GENERATED {path}"] and check.drift == 1
    assert emitted == [f"GENERATE {path}"] and result.generated == 1
    assert path.read_bytes() == expected


def test_shared_rules_alone_can_push_a_generated_file_over_the_limit(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    big = make_rule(source, "big", "x" * (GENERATED_LIMIT - len(GENERATED_HEADER) - 2))
    assert len(render_host_file({"big": big}, {}).encode("utf-8")) == GENERATED_LIMIT + 1
    config = settings(tmp_path, source)
    run(config)
    reported: list[str] = []

    check = run(config.with_mode(Mode.CHECK), emit=reported.append)

    assert reported == [
        f"MISMATCH OVERSIZE {generated_file(config, host)} is {GENERATED_LIMIT + 1} bytes; limit 32768"
        for host in SINGLE_FILE_HOSTS
    ]
    assert check.drift == len(SINGLE_FILE_HOSTS)


@pytest.mark.parametrize(
    ("mode", "generate", "link"),
    [(Mode.DRY_RUN, "WOULD GENERATE", "WOULD LINK"), (Mode.CHECK, "MISMATCH GENERATED", "MISMATCH")],
)
def test_read_only_run_reports_generated_files_and_instruction_links_and_writes_nothing(
    tmp_path: Path, mode: Mode, generate: str, link: str
) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone")
    config = settings(tmp_path, source, mode=mode)
    make_host_roots(config, "codex")
    reported: list[str] = []

    result = run(config, emit=reported.append)

    for host in SINGLE_FILE_HOSTS:
        assert f"{generate} {generated_file(config, host)}" in reported
    codex = instruction_link(config, "codex")
    assert f"{link} {codex} -> {generated_file(config, 'codex')}" in reported
    assert not config.agents_root.exists()
    assert not os.path.lexists(codex)
    assert result.generated == 0 and result.linked == 0
    assert result.drift >= len(SINGLE_FILE_HOSTS) + 1


# --- instruction links ---------------------------------------------------------------------


def test_recorded_instruction_link_replaced_by_a_file_is_unmanaged_and_keeps_its_record(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone")
    config = settings(tmp_path, source)
    make_host_roots(config, "codex", "copilot")
    run(config)
    codex = instruction_link(config, "codex")
    copilot = instruction_link(config, "copilot")
    before = read_state(config)["rules"]["instructions"]
    codex.unlink()
    codex.write_text("mine\n")
    elsewhere = tmp_path / "elsewhere.md"
    elsewhere.write_text("elsewhere\n")
    copilot.unlink()
    copilot.symlink_to(elsewhere)
    before_sync: list[str] = []
    emitted: list[str] = []
    reported: list[str] = []

    stale = run(config.with_mode(Mode.CHECK), emit=before_sync.append)
    result = run(config, emit=emitted.append)
    check = run(config.with_mode(Mode.CHECK), emit=reported.append)

    assert before_sync == [f"UNMANAGED {codex}", f"MISMATCH {copilot} -> {generated_file(config, 'copilot')}"]
    assert stale.drift >= 1
    assert f"UNMANAGED {codex}" in emitted and result.unmanaged == 1
    assert codex.read_text() == "mine\n" and not codex.is_symlink()
    assert before == {"codex": str(codex), "copilot": str(copilot)}
    assert read_state(config)["rules"]["instructions"] == before
    copilot_target = generated_file(config, "copilot")
    assert any(line.startswith("LINK[") and line.endswith(f"{copilot} -> {copilot_target}") for line in emitted)
    assert copilot.resolve() == copilot_target.resolve() and elsewhere.read_text() == "elsewhere\n"
    assert len(list((config.agents_root / "backups").glob("*/instructions/copilot/*"))) == 1
    assert list((config.agents_root / "backups").glob("*/instructions/codex/*")) == []
    assert reported == [f"UNMANAGED {codex}"]
    assert check.drift == 0
    assert not any(line.startswith("MISMATCH STATE") for line in reported)


# --- refusals and orphans ------------------------------------------------------------------


def test_duplicate_rule_across_sources_writes_nothing(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_skill(first, "portable")
    make_rule(first, "tone")
    make_rule(second, "tone")
    config = settings(tmp_path, first, second)
    make_host_roots(config, "codex")

    with pytest.raises(BraidError, match="duplicate rule name 'tone'"):
        run(config)

    assert not config.agents_root.exists()
    assert not config.claude_root.exists()
    assert list((tmp_path / "home" / ".codex").iterdir()) == []


def test_check_reports_a_stray_rule_link_into_the_union_view_as_an_orphan(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone")
    config = enroll(settings(tmp_path, source))
    run(config)
    rules_dir = config.claude_root / "rules"
    stray = rules_dir / "stray.md"
    stray.symlink_to(config.agents_root / "rules" / "tone" / "RULE.md")
    kiro_stray = kiro_root(config) / "steering" / "stray.md"
    kiro_stray.symlink_to(config.agents_root / "rules" / "tone" / "RULE.md")
    outside = tmp_path / "outside.md"
    outside.write_text("mine")
    (rules_dir / "own.md").symlink_to(outside)
    (rules_dir / "notes.md").write_text("notes")
    reported: list[str] = []

    result = run(config.with_mode(Mode.CHECK), emit=reported.append)

    assert sorted(reported) == sorted([f"MISMATCH ORPHAN {stray}", f"MISMATCH ORPHAN {kiro_stray}"])
    assert result.drift == 2
    assert stray.is_symlink() and kiro_stray.is_symlink() and (rules_dir / "own.md").is_symlink()
    assert (rules_dir / "notes.md").read_text() == "notes"


# --- skipped hosts and ignored counts ------------------------------------------------------


@pytest.mark.parametrize("skipped", ["claude", "kiro"])
def test_skipped_directory_host_carries_its_previous_projection_over(tmp_path: Path, skipped: str) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone")
    config = enroll(settings(tmp_path, source))
    run(config)
    make_rule(source, "later")
    flag = {"claude": "project_claude", "kiro": "project_kiro"}[skipped]
    other = {"claude": "kiro", "kiro": "claude"}[skipped]
    roots = {"claude": config.claude_root / "rules", "kiro": kiro_root(config) / "steering"}

    run(replace(config, **{flag: False}))

    projected = read_state(config)["rules"]["projected"]
    assert projected[skipped] == {"tone": str(config.agents_root / "rules" / "tone" / "RULE.md")}
    assert set(projected[other]) == {"tone", "later"}
    assert (roots[skipped] / "tone.md").is_symlink()
    assert not os.path.lexists(roots[skipped] / "later.md")
    assert (roots[other] / "later.md").is_symlink()


@pytest.mark.parametrize(
    ("enrolled", "project_claude", "expected"),
    [(True, True, 9), (False, True, 7), (True, False, 7)],
    ids=["claude-and-kiro", "claude-only", "kiro-only"],
)
def test_ignored_rule_counts_once_per_host_projection_that_runs(
    tmp_path: Path, enrolled: bool, project_claude: bool, expected: int
) -> None:
    source = tmp_path / "personal"
    make_rule(source, "secret", "Shared secret.")
    make_rule(source, "tone", "Tone.")
    make_host_rule(source, "codex", "codex-secret", "Codex secret.")
    make_host_rule(source, "claude", "claude-secret")
    make_host_rule(source, "kiro", "kiro-secret")
    make_host_rule(source, "kiro", "kiro-kept")
    policy = write_policy(tmp_path / "policy", "secret", "codex-secret", "claude-secret", "kiro-secret")
    config = replace(settings(tmp_path, source, policy_files=(policy,)), project_claude=project_claude)
    config = enroll(config) if enrolled else config

    result = run(config)

    assert result.ignored == expected
    projected = read_state(config)["rules"]["projected"]
    assert ("kiro" in projected) is enrolled
    codex = generated_file(config, "codex").read_text()
    assert "Tone." in codex and "Shared secret." not in codex and "Codex secret." not in codex
    if project_claude:
        assert sorted(path.name for path in (config.claude_root / "rules").iterdir()) == ["tone.md"]
        assert set(projected["claude"]) == {"tone"}
    if enrolled:
        assert sorted(path.name for path in (kiro_root(config) / "steering").iterdir()) == ["kiro-kept.md", "tone.md"]
        assert set(projected["kiro"]) == {"tone", "kiro-kept"}
    assert (config.agents_root / "hosts" / "claude" / "rules" / "claude-secret").is_symlink()


# --- Windows removal -----------------------------------------------------------------------


def sync_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Settings, Path, Path]:
    kept = tmp_path / "kept"
    make_rule(kept, "kept", "Kept.")
    dropped = tmp_path / "dropped"
    make_rule(dropped, "tone", "Tone.")
    config = replace(settings(tmp_path, kept, dropped), platform="nt")
    deny_file_symlinks(monkeypatch)
    run(config)
    hard_link = config.claude_root / "rules" / "tone.md"
    assert hard_link.is_file() and not hard_link.is_symlink()
    return config, kept, dropped


def test_windows_hard_link_of_a_dropped_source_is_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, kept, _dropped = sync_on_windows(tmp_path, monkeypatch)
    hard_link = config.claude_root / "rules" / "tone.md"
    emitted: list[str] = []

    run(replace(config, sources=(kept,)), emit=emitted.append)

    assert [line for line in emitted if line.startswith("REMOVE ")] == [
        f"REMOVE {hard_link}",
        f"REMOVE {config.agents_root / 'rules' / 'tone'}",
    ]
    assert not os.path.lexists(hard_link)
    assert (config.claude_root / "rules" / "kept.md").samefile(kept / "rules" / "kept" / "RULE.md")
    assert not (config.claude_root / "rules-backup").exists()


def test_windows_hard_link_of_a_deleted_rule_is_backed_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, kept, dropped = sync_on_windows(tmp_path, monkeypatch)
    hard_link = config.claude_root / "rules" / "tone.md"
    shutil.rmtree(dropped / "rules" / "tone")
    emitted: list[str] = []

    run(config, emit=emitted.append)

    assert any(line.startswith("BACKUP ") and str(hard_link) in line for line in emitted)
    assert [backup.read_text() for backup in (config.claude_root / "rules-backup").rglob("tone.md")] == ["Tone."]
    assert f"REMOVE {config.agents_root / 'rules' / 'tone'}" in emitted
    assert not os.path.lexists(hard_link)
    assert (config.claude_root / "rules" / "kept.md").samefile(kept / "rules" / "kept" / "RULE.md")


def test_windows_recorded_instruction_file_not_regenerated_this_run_is_unmanaged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone", "Tone.")
    config = replace(settings(tmp_path, source), platform="nt")
    make_host_roots(config, "codex")
    deny_file_symlinks(monkeypatch)
    run(config)
    codex = instruction_link(config, "codex")
    assert codex.is_file() and not codex.is_symlink() and codex.samefile(generated_file(config, "codex"))
    before = read_state(config)["rules"]["instructions"]
    codex.unlink()
    codex.write_text("mine\n")
    emitted: list[str] = []

    result = run(config, emit=emitted.append)

    assert emitted == [f"UNMANAGED {codex}"] and result.unmanaged == 1
    assert codex.read_text() == "mine\n" and not codex.samefile(generated_file(config, "codex"))
    assert read_state(config)["rules"]["instructions"] == before == {"codex": str(codex)}
    assert not (config.agents_root / "backups").exists()


USER_FILE_CONTENTS = {
    "short": lambda old: b"mine\n",
    "longer-than-header": lambda old: b"m" * (len(GENERATED_HEADER.encode()) + 64),
    "byte-copy-of-generated": lambda old: old,
    "edited-copy-of-generated": lambda old: old + b"\nMy own edit.\n",
}


@pytest.mark.parametrize("content", list(USER_FILE_CONTENTS.values()), ids=list(USER_FILE_CONTENTS))
def test_windows_user_file_at_a_recorded_instruction_path_stays_unmanaged_when_its_generated_file_is_rewritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: Callable[[bytes], bytes]
) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone", "Tone.")
    config = replace(settings(tmp_path, source), platform="nt")
    make_host_roots(config, "codex", "copilot")
    deny_file_symlinks(monkeypatch)
    run(config)
    codex = instruction_link(config, "codex")
    copilot = instruction_link(config, "copilot")
    for host, link in (("codex", codex), ("copilot", copilot)):
        assert link.is_file() and not link.is_symlink() and link.samefile(generated_file(config, host))
    before = read_state(config)["rules"]["instructions"]
    mine = content(generated_file(config, "codex").read_bytes())
    codex.unlink()
    codex.write_bytes(mine)
    (source / "rules" / "tone" / "RULE.md").write_text("Tone, revised.", encoding="utf-8")
    emitted: list[str] = []

    result = run(config, emit=emitted.append)

    assert f"UNMANAGED {codex}" in emitted and result.unmanaged == 1
    assert not any(line.startswith(("LINK", "BACKUP")) and str(codex) in line for line in emitted)
    assert codex.read_bytes() == mine and not codex.samefile(generated_file(config, "codex"))
    assert before == {"codex": str(codex), "copilot": str(copilot)}
    assert read_state(config)["rules"]["instructions"] == before
    assert not (config.agents_root / "backups").exists()
    for host in ("codex", "copilot"):
        assert f"GENERATE {generated_file(config, host)}" in emitted
        assert generated_file(config, host).read_text() == f"{GENERATED_HEADER}\n\nTone, revised.\n"
    assert f"LINK[hardlink] {copilot} -> {generated_file(config, 'copilot')}" in emitted
    assert f"UNMANAGED {copilot}" not in emitted
    assert copilot.samefile(generated_file(config, "copilot"))


def test_windows_separate_copy_of_unchanged_generated_file_at_a_recorded_path_is_unmanaged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone", "Tone.")
    config = replace(settings(tmp_path, source), platform="nt")
    make_host_roots(config, "codex")
    deny_file_symlinks(monkeypatch)
    run(config)
    codex = instruction_link(config, "codex")
    assert codex.samefile(generated_file(config, "codex"))
    before = read_state(config)["rules"]["instructions"]
    current = generated_file(config, "codex").read_bytes()
    assert current.startswith(GENERATED_HEADER.encode())
    codex.unlink()
    codex.write_bytes(current)
    emitted: list[str] = []

    result = run(config, emit=emitted.append)

    assert emitted == [f"UNMANAGED {codex}"] and result.unmanaged == 1 and result.linked == 0
    assert codex.read_bytes() == current and not codex.samefile(generated_file(config, "codex"))
    assert read_state(config)["rules"]["instructions"] == before == {"codex": str(codex)}
    assert not (config.agents_root / "backups").exists()


def test_sync_rules_accepts_all_six_arguments_positionally(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "tone", "Tone.")
    make_host_rule(source, "codex", "codex-only", "Codex only.")
    config = settings(tmp_path, source)
    config.agents_root.mkdir(parents=True)
    inventory = discover_rules(config.sources)
    emitted: list[str] = []
    result = Result()

    state = sync_rules(config, inventory, frozenset(), None, result, emitted.append)

    assert isinstance(state, RuleState)
    assert state.generated == {host: str(generated_file(config, host)) for host in SINGLE_FILE_HOSTS}
    assert set(state.union) == {"tone"} and set(state.hosts) == {"codex"}
    assert set(state.hosts["codex"]) == {"codex-only"}
    for host in SINGLE_FILE_HOSTS:
        assert f"GENERATE {generated_file(config, host)}" in emitted
    assert result.generated == len(SINGLE_FILE_HOSTS)
    assert generated_file(config, "codex").read_text() == f"{GENERATED_HEADER}\n\nTone.\n\nCodex only.\n"
    assert generated_file(config, "copilot").read_text() == f"{GENERATED_HEADER}\n\nTone.\n"
    again: list[str] = []
    second = Result()

    sync_rules(config, inventory, frozenset({"tone"}), state, second, again.append)

    assert not any(line.startswith("BACKUP ") for line in again)
    assert not (config.agents_root / "backups").exists()
    assert second.generated == len(SINGLE_FILE_HOSTS)
    for host in SINGLE_FILE_HOSTS:
        expected = render_host_file({}, inventory.hosts.get(host, {})).encode("utf-8")
        assert generated_file(config, host).read_bytes() == expected
        assert b"Tone." not in expected


# --- pre-existing files in directory hosts -------------------------------------------------


def test_real_file_at_a_directory_host_rule_path_is_backed_up_before_linking(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    tone = make_rule(source, "tone", "Tone.")
    config = enroll(settings(tmp_path, source))
    claude_file = config.claude_root / "rules" / "tone.md"
    kiro_file = kiro_root(config) / "steering" / "tone.md"
    for path, text in ((claude_file, "claude mine\n"), (kiro_file, "kiro mine\n")):
        path.parent.mkdir(parents=True)
        path.write_text(text)
    emitted: list[str] = []

    run(config, emit=emitted.append)

    for path, backups, text in (
        (claude_file, config.claude_root / "rules-backup", "claude mine\n"),
        (kiro_file, kiro_root(config) / "steering-backup", "kiro mine\n"),
    ):
        assert [backup.read_text() for backup in backups.rglob("tone.md")] == [text]
        assert any(line.startswith(f"BACKUP {path} -> ") for line in emitted)
        assert path.is_symlink() and path.resolve() == (tone / "RULE.md").resolve()
