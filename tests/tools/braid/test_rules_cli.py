from __future__ import annotations

import os
from pathlib import Path

import braid.cli as braid_cli
import pytest
from braid.cli import cli
from braid.commands.compose.compose import CommandCompose
from braid.domain.engine import ComposeRequest
from click.testing import CliRunner
from rich.console import Console

from tests.tools.braid.helpers import make_host_rule, make_rule

SINGLE_FILE_HOSTS = ("codex", "copilot", "pi", "gemini")


@pytest.fixture(autouse=True)
def narrow_console(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(braid_cli.console, "console", Console(width=80, color_system=None))


def roots(tmp_path: Path, source: Path) -> list[str]:
    return [
        "--agents-root",
        str(tmp_path / "home" / ".agents"),
        "--claude-root",
        str(tmp_path / "home" / ".claude"),
        "--config-root",
        str(tmp_path / "empty-config"),
        "--source",
        str(source),
    ]


def configured_roots(tmp_path: Path, *sources: Path) -> list[str]:
    sources_d = tmp_path / "config" / "sources.d"
    sources_d.mkdir(parents=True)
    (sources_d / "list").write_text("".join(f"{source}\n" for source in sources))
    return [
        "--agents-root",
        str(tmp_path / "home" / ".agents"),
        "--claude-root",
        str(tmp_path / "home" / ".claude"),
        "--config-root",
        str(tmp_path / "config"),
    ]


def generated(tmp_path: Path, host: str) -> Path:
    return tmp_path / "home" / ".agents" / "hosts" / host / "AGENTS.md"


def hand_made_codex_link(tmp_path: Path) -> Path:
    """A ``~/.codex/AGENTS.md`` symlink the user made by hand, pointing outside braid."""
    elsewhere = tmp_path / "hand-kept" / "AGENTS.md"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_text("hand-kept instructions\n")
    link = tmp_path / "home" / ".codex" / "AGENTS.md"
    link.parent.mkdir(parents=True)
    link.symlink_to(elsewhere)
    return link


def hand_made_gemini_file(tmp_path: Path) -> Path:
    path = tmp_path / "home" / ".gemini" / "GEMINI.md"
    path.parent.mkdir(parents=True)
    path.write_text("hand-kept gemini\n")
    return path


def unmanaged_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("UNMANAGED ")]


def test_sync_summary_counts_generated_files_and_unmanaged_host_paths(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "safety", "Be safe.")
    hand_made_codex_link(tmp_path)
    (tmp_path / "home" / ".copilot").mkdir(parents=True)
    runner = CliRunner()

    first = runner.invoke(cli, roots(tmp_path, source))
    second = runner.invoke(cli, roots(tmp_path, source))

    assert first.exit_code == 0
    assert first.output.splitlines()[-1] == (
        "braid: 3 linked, 4 generated, 0 current, 0 ignored, 0 removed, 0 backed up, 0 configured, 1 unmanaged, "
        "7 change(s)"
    )
    assert sum(line.startswith("GENERATE ") for line in first.output.splitlines()) == 4
    assert second.exit_code == 0
    assert second.output.splitlines()[-1] == (
        "braid: 0 linked, 0 generated, 7 current, 0 ignored, 0 removed, 0 backed up, 0 configured, 1 unmanaged, "
        "0 change(s)"
    )
    for host in SINGLE_FILE_HOSTS:
        assert "Be safe." in generated(tmp_path, host).read_text()


def test_sync_without_host_paths_reports_zero_unmanaged(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "safety")

    result = CliRunner().invoke(cli, roots(tmp_path, source))

    assert result.exit_code == 0
    assert result.output.splitlines()[-1] == (
        "braid: 2 linked, 4 generated, 0 current, 0 ignored, 0 removed, 0 backed up, 0 configured, 0 unmanaged, "
        "6 change(s)"
    )
    assert unmanaged_lines(result.output) == []


def test_check_reports_an_unmanaged_host_path_and_still_exits_0(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "safety")
    codex_link = hand_made_codex_link(tmp_path)
    codex_target = os.readlink(codex_link)
    (tmp_path / "home" / ".copilot").mkdir(parents=True)
    runner = CliRunner()
    sync = runner.invoke(cli, roots(tmp_path, source))

    result = runner.invoke(cli, [*roots(tmp_path, source), "--check"])

    assert unmanaged_lines(sync.output) == [f"UNMANAGED {codex_link}"]
    assert result.exit_code == 0
    assert unmanaged_lines(result.output) == [f"UNMANAGED {codex_link}"]
    assert result.output.splitlines()[-1].startswith(
        "braid: 0 linked, 0 generated, 7 current, 0 ignored, 0 removed, 0 backed up, 0 configured, 1 unmanaged, 0 "
    )
    assert codex_link.is_symlink()
    assert os.readlink(codex_link) == codex_target
    assert codex_link.read_text() == "hand-kept instructions\n"
    copilot_link = tmp_path / "home" / ".copilot" / "copilot-instructions.md"
    assert copilot_link.resolve() == generated(tmp_path, "copilot").resolve()


def test_check_lists_every_unmanaged_host_path_once(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "safety")
    codex_link = hand_made_codex_link(tmp_path)
    gemini_file = hand_made_gemini_file(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, roots(tmp_path, source))

    result = runner.invoke(cli, [*roots(tmp_path, source), "--check"])

    assert result.exit_code == 0
    assert sorted(unmanaged_lines(result.output)) == sorted([f"UNMANAGED {codex_link}", f"UNMANAGED {gemini_file}"])
    assert ", 2 unmanaged, " in result.output.splitlines()[-1]
    assert gemini_file.read_text() == "hand-kept gemini\n"


@pytest.mark.parametrize("second_kind", ["shared", "host"])
def test_duplicate_rule_across_two_sources_exits_2_before_writing(tmp_path: Path, second_kind: str) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    make_rule(first, "safety")
    if second_kind == "shared":
        make_rule(second, "safety")
    else:
        make_host_rule(second, "codex", "safety")

    result = CliRunner().invoke(cli, configured_roots(tmp_path, first, second))

    assert result.exit_code == 2
    lines = result.output.splitlines()
    expected = f"braid: duplicate rule name 'safety': {first.resolve()} and {second}"
    assert sum("duplicate rule name" in line for line in lines) == 1
    assert lines[-1].endswith(expected)
    assert "Traceback" not in result.output
    agents_root = tmp_path / "home" / ".agents"
    assert not os.path.lexists(agents_root / ".braid-state.json")
    assert not os.path.lexists(agents_root / "rules")
    assert not os.path.lexists(agents_root / "hosts")


def test_rules_sharing_a_name_prefix_across_sources_are_not_duplicates(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    make_rule(first, "safety")
    make_rule(second, "safety-net")

    result = CliRunner().invoke(cli, configured_roots(tmp_path, first, second))

    assert result.exit_code == 0
    assert "duplicate rule name" not in result.output
    assert (tmp_path / "home" / ".agents" / "rules" / "safety").is_symlink()
    assert (tmp_path / "home" / ".agents" / "rules" / "safety-net").is_symlink()


def test_check_exits_1_on_an_edited_generated_file_and_sync_restores_it(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "safety")
    runner = CliRunner()
    runner.invoke(cli, roots(tmp_path, source))
    codex_file = generated(tmp_path, "codex")
    edited = codex_file.read_bytes() + b"hand edit\n"
    codex_file.write_bytes(edited)

    check = runner.invoke(cli, [*roots(tmp_path, source), "--check"])

    assert check.exit_code == 1
    mismatches = [line for line in check.output.splitlines() if line.startswith("MISMATCH GENERATED ")]
    assert mismatches == [f"MISMATCH GENERATED {codex_file}"]
    assert check.output.splitlines()[-1].startswith(
        "braid: 0 linked, 0 generated, 5 current, 0 ignored, 0 removed, 0 backed up, 0 configured, 0 unmanaged, 1 "
    )
    assert codex_file.read_bytes() == edited

    sync = runner.invoke(cli, roots(tmp_path, source))

    assert sync.exit_code == 0
    assert [line for line in sync.output.splitlines() if line.startswith("GENERATE ")] == [f"GENERATE {codex_file}"]
    assert codex_file.read_bytes() == generated(tmp_path, "copilot").read_bytes()
    assert runner.invoke(cli, [*roots(tmp_path, source), "--check"]).exit_code == 0


def test_check_exits_0_when_generated_files_are_untouched(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "safety")
    runner = CliRunner()
    runner.invoke(cli, roots(tmp_path, source))

    check = runner.invoke(cli, [*roots(tmp_path, source), "--check"])

    assert check.exit_code == 0
    assert not any(line.startswith("MISMATCH") for line in check.output.splitlines())


def compose_request(tmp_path: Path, source: Path) -> ComposeRequest:
    config_root = tmp_path / "config"
    config_root.mkdir(exist_ok=True)
    return ComposeRequest(
        agents_root=tmp_path / "home" / ".agents",
        claude_root=tmp_path / "home" / ".claude",
        config_root=config_root,
        sources=(source,),
    )


def test_compose_metadata_carries_one_unmanaged_host_path(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "safety")
    hand_made_codex_link(tmp_path)

    outcome = CommandCompose(compose_request(tmp_path, source)).execute()

    assert outcome.success
    assert outcome.metadata["unmanaged"] == 1


def test_compose_metadata_carries_two_unmanaged_host_paths(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "safety")
    hand_made_codex_link(tmp_path)
    hand_made_gemini_file(tmp_path)

    outcome = CommandCompose(compose_request(tmp_path, source)).execute()

    assert outcome.success
    assert outcome.metadata["unmanaged"] == 2


def test_compose_error_result_carries_zero_unmanaged(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_rule(source, "safety")
    make_host_rule(source, "codex", "safety")
    hand_made_codex_link(tmp_path)

    outcome = CommandCompose(compose_request(tmp_path, source)).execute()

    assert not outcome.success
    assert "duplicate rule name 'safety'" in str(outcome.error)
    assert outcome.metadata["unmanaged"] == 0
