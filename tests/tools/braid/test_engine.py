from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from braid.domain import engine
from braid.domain.engine import (
    BraidError,
    KiroAgentEdit,
    KiroRegistration,
    Mode,
    Result,
    Settings,
    create_directory_link,
    read_configured_sources,
    run,
    select_kiro,
    sync_kiro_agent,
)

from tests.tools.braid.helpers import enroll, kiro_root, make_skill, read_state, settings, write_agent


def test_sync_composes_union_and_projects_only_eligible_skills(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    portable = make_skill(source, "portable")
    make_skill(source, "plugin-owned")
    policy = source / ".braidignore"
    policy.write_text("plugin-owned\n")

    config = settings(tmp_path, source, policy_files=(policy,))
    claude_only = config.claude_root / "skills" / "claude-only"
    plugin_owned = config.claude_root / "skills" / "plugin-owned"
    claude_only.mkdir(parents=True)
    plugin_owned.mkdir(parents=True)
    (claude_only / "keep").write_text("yes")
    (plugin_owned / "keep").write_text("plugin")

    result = run(config)

    union_link = config.agents_root / "skills" / "portable"
    claude_link = config.claude_root / "skills" / "portable"
    assert union_link.is_symlink()
    assert union_link.resolve() == portable.resolve()
    assert claude_link.is_symlink()
    assert claude_link.resolve() == portable.resolve()
    assert (claude_only / "keep").read_text() == "yes"
    assert (plugin_owned / "keep").read_text() == "plugin"
    assert result.linked == 3
    assert result.ignored == 1

    checked = run(config.with_mode(Mode.CHECK))
    assert checked.drift == 0
    assert checked.current == 3


def test_duplicate_names_fail_before_writing(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_skill(first, "collision")
    make_skill(second, "collision")
    config = settings(tmp_path, first, second)

    with pytest.raises(BraidError, match="duplicate skill name"):
        run(config)

    assert not config.agents_root.exists()


def test_dry_run_reports_drift_without_writing(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    skill = make_skill(source, "portable")
    config = settings(tmp_path, source, mode=Mode.DRY_RUN)
    reported: list[str] = []

    result = run(config, emit=reported.append)

    assert result.drift == 2
    union_link = config.agents_root / "skills" / "portable"
    assert reported == [
        f"WOULD LINK {union_link} -> {skill.resolve()}",
        f"WOULD LINK {config.claude_root / 'skills' / 'portable'} -> {union_link}",
    ]
    assert not config.agents_root.exists()
    assert not config.claude_root.exists()


@pytest.mark.parametrize("mode", [Mode.DRY_RUN, Mode.CHECK])
def test_preview_and_check_leave_a_colliding_real_folder_in_place(tmp_path: Path, mode: Mode) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    config = settings(tmp_path, source, mode=mode)
    collisions = [root / "skills" / "portable" for root in (config.agents_root, config.claude_root)]
    for collision in collisions:
        collision.mkdir(parents=True)
        (collision / "original").write_text("keep")

    result = run(config)

    for collision in collisions:
        assert collision.is_dir()
        assert not collision.is_symlink()
        assert (collision / "original").read_text() == "keep"
    assert not (config.agents_root / "backups").exists()
    assert not (config.claude_root / "skills-backup").exists()
    assert (result.drift, result.backed_up) == (2, 0)


def test_real_union_collision_is_backed_up_before_linking(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    expected = make_skill(source, "portable")
    config = settings(tmp_path, source)
    collision = config.agents_root / "skills" / "portable"
    collision.mkdir(parents=True)
    (collision / "original").write_text("keep")

    result = run(config)

    assert collision.is_symlink()
    assert collision.resolve() == expected.resolve()
    backups = list((config.agents_root / "backups").glob("*/compose/portable/original"))
    assert len(backups) == 1
    assert backups[0].read_text() == "keep"
    assert result.backed_up == 1


def test_real_claude_collision_is_backed_up_before_linking(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    skill = make_skill(source, "portable")
    config = settings(tmp_path, source)
    collision = config.claude_root / "skills" / "portable"
    collision.mkdir(parents=True)
    (collision / "original").write_text("keep")
    reported: list[str] = []

    result = run(config, emit=reported.append)

    union_link = config.agents_root / "skills" / "portable"
    assert collision.is_symlink()
    assert collision.resolve() == skill.resolve()
    backups = list((config.claude_root / "skills-backup").glob("*/project/portable"))
    assert [(backup / "original").read_text() for backup in backups] == ["keep"]
    assert result.backed_up == 1
    assert reported == [
        f"LINK[symlink] {union_link} -> {skill.resolve()}",
        f"BACKUP {collision} -> {backups[0]}",
        f"LINK[symlink] {collision} -> {union_link}",
    ]


def test_stale_cleanup_removes_only_manifest_owned_links(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    skill = make_skill(source, "temporary")
    config = settings(tmp_path, source)
    unowned = config.agents_root / "skills" / "manual"
    unowned.mkdir(parents=True)
    (unowned / "keep").write_text("yes")
    run(config)

    shutil.rmtree(skill)
    result = run(config)

    assert not os.path.lexists(config.agents_root / "skills" / "temporary")
    assert (unowned / "keep").read_text() == "yes"
    assert result.removed == 2


def test_existing_source_tree_is_not_replaced_during_transition(tmp_path: Path) -> None:
    agents_root = tmp_path / "home" / ".agents"
    source_skill = make_skill(agents_root, "portable")
    config = Settings(
        sources=(agents_root,),
        agents_root=agents_root,
        claude_root=tmp_path / "home" / ".claude",
        mode=Mode.SYNC,
    )

    run(config)

    assert source_skill.is_dir()
    assert not source_skill.is_symlink()
    assert (config.claude_root / "skills" / "portable").is_symlink()
    state = json.loads((agents_root / ".braid-state.json").read_text())
    assert state["union"] == {}


def test_no_claude_preserves_existing_projection_and_state(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    config = settings(tmp_path, source)
    run(config)
    claude_link = config.claude_root / "skills" / "portable"

    result = run(replace(config, project_claude=False))

    assert result.drift == 0
    assert claude_link.is_symlink()
    state = json.loads((config.agents_root / ".braid-state.json").read_text())
    assert "portable" in state["hosts"]["claude"]


def test_windows_symlink_privilege_failure_falls_back_to_junction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    destination = tmp_path / "destination"
    target.mkdir()
    calls: list[list[str]] = []

    error = OSError("symlink privilege unavailable")
    error.winerror = 1314

    def denied(*_args: object, **_kwargs: object) -> None:
        raise error

    class Completed:
        returncode = 0
        stdout = "junction created"
        stderr = ""

    def runner(command: list[str], **_kwargs: object) -> Completed:
        calls.append(command)
        return Completed()

    monkeypatch.setattr(os, "symlink", denied)

    backend = create_directory_link(destination, target, platform="nt", runner=runner)

    assert backend == "junction"
    assert calls == [["cmd", "/c", "mklink", "/J", str(destination), str(target)]]


def deny_symlink(monkeypatch: pytest.MonkeyPatch, winerror: int) -> None:
    error = OSError("symlink denied")
    error.winerror = winerror

    def denied(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(os, "symlink", denied)


def test_windows_junction_that_mklink_fails_to_create_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    deny_symlink(monkeypatch, 1314)

    class Failed:
        returncode = 1
        stdout = ""
        stderr = "Access is denied.\n"

    with pytest.raises(BraidError, match="cannot create junction .*: Access is denied.$"):
        create_directory_link(tmp_path / "destination", target, platform="nt", runner=lambda *_a, **_k: Failed())


def test_windows_link_error_other_than_privilege_is_not_retried_as_a_junction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    deny_symlink(monkeypatch, 3)
    calls: list[object] = []

    def runner(command: object, **_kwargs: object) -> object:
        calls.append(command)
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with pytest.raises(BraidError, match="cannot link"):
        create_directory_link(tmp_path / "destination", target, platform="nt", runner=runner)

    assert calls == []


def test_configured_sources_support_comments_home_and_relative_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    config_root = home / ".config" / "agent-skills"
    source_list = config_root / "sources.d" / "work"
    source_list.parent.mkdir(parents=True)
    source_list.write_text("# private source\n~/work-skills\n../../shared-skills\n")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    sources = read_configured_sources(config_root)

    assert sources == (
        (home / "work-skills").resolve(),
        (source_list.parent / "../../shared-skills").resolve(),
    )


def test_a_symlinked_skill_directory_outside_the_source_is_not_inventoried(
    tmp_path: Path,
) -> None:
    source = tmp_path / "personal"
    kept = make_skill(source, "kept")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("---\nname: evil\ndescription: Test evil.\n---\n\n# evil\n")
    (source / "skills" / "evil").symlink_to(outside, target_is_directory=True)

    inventory = engine.discover_inventory([source])

    assert inventory == {"kept": kept.resolve()}


def test_kiro_gets_every_skill_including_those_ignored_for_claude(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plugin_owned = make_skill(source, "plugin-owned")
    policy = source / ".braidignore"
    policy.write_text("plugin-owned\n")
    config = enroll(settings(tmp_path, source, policy_files=(policy,)))

    run(config)

    kiro_skills = kiro_root(config) / "skills"
    assert (kiro_skills / "portable").is_symlink()
    assert (kiro_skills / "plugin-owned").resolve() == plugin_owned.resolve()
    assert not os.path.lexists(config.claude_root / "skills" / "plugin-owned")
    assert run(config.with_mode(Mode.CHECK)).drift == 0


def test_later_runs_maintain_kiro_without_repeating_the_flags(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    run(enroll(plain))
    make_skill(source, "added-later")

    run(plain)

    assert (kiro_root(plain) / "skills" / "added-later").is_symlink()
    assert run(plain.with_mode(Mode.CHECK)).drift == 0


@pytest.mark.parametrize("mode", [Mode.DRY_RUN, Mode.CHECK])
def test_preview_and_check_never_record_kiro_enrollment(tmp_path: Path, mode: Mode) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    run(plain)

    result = run(replace(enroll(plain), mode=mode))

    assert result.drift > 0
    assert not kiro_root(plain).exists()
    assert "kiro" not in read_state(plain)
    assert run(plain.with_mode(Mode.CHECK)).drift == 0


def test_no_kiro_skips_kiro_for_one_run_and_keeps_its_enrollment(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    run(enroll(plain))
    make_skill(source, "added-later")
    added_later = kiro_root(plain) / "skills" / "added-later"

    run(replace(plain, project_kiro=False))

    assert not os.path.lexists(added_later)
    state = read_state(plain)
    assert Path(state["kiro"]["root"]) == kiro_root(plain).resolve()
    assert "portable" in state["hosts"]["kiro"]
    run(plain)
    assert added_later.is_symlink()


def test_kiro_name_collision_is_backed_up_and_unmanaged_skills_stay(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    kiro_skills = kiro_root(plain) / "skills"
    (kiro_skills / "portable").mkdir(parents=True)
    (kiro_skills / "portable" / "original").write_text("keep")
    (kiro_skills / "manual").mkdir()
    (kiro_skills / "manual" / "keep").write_text("yes")

    result = run(enroll(plain))

    assert (kiro_skills / "portable").is_symlink()
    backups = (kiro_root(plain) / "skills-backup").glob("*/project/portable/original")
    assert [backup.read_text() for backup in backups] == ["keep"]
    assert (kiro_skills / "manual" / "keep").read_text() == "yes"
    assert result.backed_up == 1


def test_selected_agent_gains_the_skill_resource_and_keeps_everything_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    agent = write_agent(plain, "dev", {"name": "dev", "resources": ["file://README.md"], "tools": ["read"]})
    agent.chmod(0o640)
    original = agent.read_bytes()
    reported: list[str] = []

    result = run(enroll(plain, "dev"), emit=reported.append)

    assert json.loads(agent.read_text()) == {
        "name": "dev",
        "resources": ["file://README.md", "skill://~/.kiro/skills/*/SKILL.md"],
        "tools": ["read"],
    }
    assert agent.stat().st_mode & 0o777 == 0o640
    assert (result.configured, result.backed_up) == (1, 1)
    backups = list((kiro_root(plain) / "agent-backup").glob("*/agents/dev.json"))
    assert [backup.read_bytes() for backup in backups] == [original]
    assert reported[-2:] == [f"BACKUP {agent} -> {backups[0]}", f"CONFIGURE {agent}"]

    again = run(plain)

    assert (again.configured, again.drift) == (0, 0)
    assert list((kiro_root(plain) / "agent-backup").glob("*/agents/dev.json")) == backups


@pytest.mark.parametrize(
    "existing",
    ["skill://~/.agents/skills/*/SKILL.md", "skill://~/.kiro/skills/*/SKILL.md"],
    ids=["shared-union", "kiro-view"],
)
def test_agent_already_reading_the_skills_is_left_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: str
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    agent = write_agent(plain, "dev", {"resources": [existing]})
    original = agent.read_bytes()

    result = run(enroll(plain, "dev"))

    assert agent.read_bytes() == original
    assert result.configured == 0
    assert not (kiro_root(plain) / "agent-backup").exists()


def test_an_unrelated_home_skill_resource_does_not_stand_in_for_the_kiro_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    unrelated = "skill://~/notes/*/SKILL.md"
    agent = write_agent(plain, "dev", {"resources": [unrelated]})

    result = run(enroll(plain, "dev"))

    assert json.loads(agent.read_text())["resources"] == [unrelated, "skill://~/.kiro/skills/*/SKILL.md"]
    assert result.configured == 1


def test_enrolling_a_second_agent_keeps_the_first_enrolled(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    write_agent(plain, "dev", {"resources": []})
    qa = write_agent(plain, "qa", {"resources": []})
    run(enroll(plain, "dev"))

    run(enroll(plain, "qa"))

    assert read_state(plain)["kiro"]["agents"] == ["dev", "qa"]
    assert json.loads(qa.read_text())["resources"] == ["skill://~/.kiro/skills/*/SKILL.md"]


def test_project_relative_skill_resource_does_not_stand_in_for_the_global_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    relative = "skill://.kiro/skills/*/SKILL.md"
    agent = write_agent(plain, "dev", {"resources": [relative]})
    # Even run from home, where the relative path happens to name the same files.
    monkeypatch.chdir(tmp_path / "home")

    run(enroll(plain, "dev"))

    assert json.loads(agent.read_text())["resources"] == [
        relative,
        "skill://~/.kiro/skills/*/SKILL.md",
    ]


UNUSABLE_AGENTS = {
    "missing": None,
    "malformed": "{not json",
    "not-an-object": "[]",
    "resources-not-a-list": '{"resources": "skill://x"}',
}


@pytest.mark.parametrize("content", UNUSABLE_AGENTS.values(), ids=UNUSABLE_AGENTS.keys())
def test_unusable_agent_config_is_refused_before_anything_is_written(tmp_path: Path, content: str | None) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    agent = kiro_root(plain) / "agents" / "dev.json"
    if content is not None:
        agent.parent.mkdir(parents=True)
        agent.write_text(content)

    with pytest.raises(BraidError, match="Kiro agent"):
        run(enroll(plain, "dev"))

    assert not plain.agents_root.exists()
    assert not (kiro_root(plain) / "skills").exists()


def test_symlinked_agent_config_is_refused_and_its_target_left_alone(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    target = tmp_path / "elsewhere.json"
    target.write_text('{"resources": []}')
    agent = kiro_root(plain) / "agents" / "dev.json"
    agent.parent.mkdir(parents=True)
    agent.symlink_to(target)

    with pytest.raises(BraidError, match="symlinked Kiro agent"):
        run(enroll(plain, "dev"))

    assert target.read_text() == '{"resources": []}'
    assert not plain.agents_root.exists()


@pytest.mark.parametrize("mode", [Mode.DRY_RUN, Mode.CHECK])
def test_preview_and_check_report_a_missing_agent_resource_without_writing(tmp_path: Path, mode: Mode) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    agent = write_agent(plain, "dev", {"resources": []})
    original = agent.read_bytes()
    run(enroll(plain, "dev"))
    agent.write_bytes(original)
    reported: list[str] = []

    result = run(plain.with_mode(mode), emit=reported.append)

    assert result.drift == 1
    verb = {Mode.CHECK: "MISMATCH RESOURCE", Mode.DRY_RUN: "WOULD CONFIGURE"}[mode]
    assert reported == [f"{verb} {agent}"]
    assert agent.read_bytes() == original
    assert len(list((kiro_root(plain) / "agent-backup").glob("*/agents/dev.json"))) == 1


def test_forgetting_an_agent_stops_managing_it_and_leaves_its_resource(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    agent = write_agent(plain, "dev", {"resources": []})
    run(enroll(plain, "dev"))
    configured = agent.read_bytes()

    run(replace(plain, forget_kiro_agents=("dev",)))

    assert agent.read_bytes() == configured
    assert read_state(plain)["kiro"]["agents"] == []
    agent.unlink()
    assert run(plain.with_mode(Mode.CHECK)).drift == 0


@pytest.mark.parametrize(
    ("request_changes", "message"),
    [
        ({"kiro_agents": ("../evil",)}, "invalid Kiro agent name"),
        ({"kiro_agents": ("dev.json",)}, "invalid Kiro agent name"),
        ({"kiro_agents": ("dev",), "forget_kiro_agents": ("dev",)}, "cannot enroll and forget"),
        ({"forget_kiro_agents": ("stranger",)}, "not registered"),
        ({"kiro_root": Path("elsewhere")}, "moving its root is unsupported"),
    ],
    ids=["path-traversal", "file-name", "enroll-and-forget", "forget-unknown", "moved-root"],
)
def test_enrollment_request_that_cannot_be_honoured_is_refused(
    tmp_path: Path, request_changes: dict[str, object], message: str
) -> None:
    enrolled = KiroRegistration(root=tmp_path / "kiro", agents=("dev",))

    with pytest.raises(BraidError, match=message):
        select_kiro(replace(settings(tmp_path), **request_changes), enrolled)


def test_forgetting_an_agent_before_kiro_is_enrolled_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BraidError, match="no registered custom agents"):
        select_kiro(replace(settings(tmp_path), forget_kiro_agents=("dev",)), None)


@pytest.mark.parametrize(
    "record",
    [{"root": "relative", "agents": []}, {"root": "/kiro", "agents": ["../evil"]}, "kiro"],
    ids=["relative-root", "path-traversal-agent", "not-an-object"],
)
def test_tampered_enrollment_record_is_refused(tmp_path: Path, record: object) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    config = settings(tmp_path, source)
    config.agents_root.mkdir(parents=True)
    state = {"version": 1, "union": {}, "hosts": {}, "kiro": record}
    (config.agents_root / ".braid-state.json").write_text(json.dumps(state))

    with pytest.raises(BraidError, match="invalid Kiro registration"):
        run(config)


def test_agent_edited_since_it_was_read_is_not_overwritten(tmp_path: Path) -> None:
    agent = tmp_path / "agents" / "dev.json"
    agent.parent.mkdir()
    agent.write_bytes(b'{"edited": "by hand"}')
    edit = KiroAgentEdit(path=agent, before=b"{}", after=b'{"resources": []}')

    with pytest.raises(BraidError, match="changed during composition"):
        sync_kiro_agent(edit, tmp_path / "backup", Mode.SYNC, Result(), print)

    assert agent.read_bytes() == b'{"edited": "by hand"}'
    assert [path.name for path in agent.parent.iterdir()] == ["dev.json"]


def test_agent_edited_while_the_new_config_is_written_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = tmp_path / "agents" / "dev.json"
    agent.parent.mkdir()
    agent.write_bytes(b"{}")
    edit = KiroAgentEdit(path=agent, before=b"{}", after=b'{"resources": []}')
    copymode = shutil.copymode

    def copymode_then_edit_by_hand(source: Path, destination: Path, *, follow_symlinks: bool = True) -> None:
        copymode(source, destination, follow_symlinks=follow_symlinks)
        agent.write_bytes(b'{"edited": "by hand"}')

    monkeypatch.setattr(shutil, "copymode", copymode_then_edit_by_hand)

    with pytest.raises(BraidError, match="changed during composition"):
        sync_kiro_agent(edit, tmp_path / "backup", Mode.SYNC, Result(), print)

    assert agent.read_bytes() == b'{"edited": "by hand"}'
    assert [path.name for path in agent.parent.iterdir()] == ["dev.json"]
