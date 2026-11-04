from __future__ import annotations

import os
from pathlib import Path

import braid.cli as braid_cli
import pytest
from braid.cli import cli
from click.testing import CliRunner
from rich.console import Console

from tests.tools.braid.helpers import kiro_root, make_skill, settings, write_agent


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


def assert_one_error_line(output: str, prefix: str, error_text: str) -> None:
    lines = output.splitlines()
    matching = [line for line in lines if prefix in line]
    assert len(matching) == 1
    assert sum(error_text in line for line in lines) == 1
    assert lines[-1] == matching[0]


def test_cli_loads_machine_policy_from_agents_root(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    make_skill(source, "machine-ignored")
    agents_root = tmp_path / "home" / ".agents"
    agents_root.mkdir(parents=True)
    (agents_root / ".braidignore").write_text("machine-ignored\n")
    claude_root = tmp_path / "home" / ".claude"

    result = CliRunner().invoke(cli, roots(tmp_path, source))

    assert result.exit_code == 0
    assert "3 change(s)" in result.output
    assert (agents_root / "skills" / "machine-ignored").is_symlink()
    assert not os.path.lexists(claude_root / "skills" / "machine-ignored")


def test_parser_documents_previously_bare_options_with_help_text() -> None:
    named_options = ("--policy", "--agents-root", "--claude-root", "--config-root", "--no-claude")

    help_by_option = {option: param.help for param in cli.params for option in param.opts if option in named_options}

    assert set(help_by_option) == set(named_options)
    help_output = " ".join(CliRunner().invoke(cli, ["--help"]).output.split())
    for help_text in help_by_option.values():
        assert isinstance(help_text, str)
        assert help_text.strip()
        assert " ".join(help_text.split()) in help_output


def test_cli_enrolls_kiro_and_reports_the_configured_agent(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    write_agent(plain, "dev", {"resources": []})
    runner = CliRunner()

    result = runner.invoke(cli, [*roots(tmp_path, source), "--kiro-root", str(kiro_root(plain)), "--kiro-agent", "dev"])

    assert result.exit_code == 0
    assert "1 configured" in result.output
    assert (kiro_root(plain) / "skills" / "portable").is_symlink()
    assert runner.invoke(cli, [*roots(tmp_path, source), "--check"]).exit_code == 0


def test_cli_enrolls_kiro_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    monkeypatch.setenv("BUVIS_BRAID_KIRO_ROOT", str(kiro_root(plain)))

    CliRunner().invoke(cli, roots(tmp_path, source))

    assert (kiro_root(plain) / "skills" / "portable").is_symlink()


def test_cli_rejects_no_kiro_combined_with_enrollment(tmp_path: Path) -> None:
    source = tmp_path / "personal"

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--no-kiro", "--kiro"])

    assert result.exit_code == 2
    assert "--no-kiro cannot be combined with Kiro enrollment options" in result.output


def test_cli_reports_a_failed_state_write_on_one_line_and_exits_2(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    state_path = tmp_path / "home" / ".agents" / ".braid-state.json"
    state_path.mkdir(parents=True)

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--no-kiro"])

    assert result.exit_code == 2
    assert_one_error_line(result.output, f"braid: cannot write Braid state {state_path}: ", "cannot write Braid state")


def test_cli_reports_an_unreadable_state_file_on_one_line_and_exits_2(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    agents_root = tmp_path / "home" / ".agents"
    agents_root.mkdir(parents=True)
    state_path = agents_root / ".braid-state.json"
    invalid_bytes = b"\xff\xfe\x00"
    state_path.write_bytes(invalid_bytes)

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--check", "--no-kiro"])

    assert result.exit_code == 2
    assert_one_error_line(result.output, f"braid: cannot read Braid state {state_path}: ", "cannot read Braid state")
    assert state_path.read_bytes() == invalid_bytes


def test_cli_check_exits_1_on_drift(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--check"])

    assert result.exit_code == 1
    summary = result.output.splitlines()[-1]
    assert summary.startswith("braid: ")
    assert "drift" in summary
    assert not os.path.lexists(tmp_path / "home" / ".agents" / ".braid-state.json")


def test_cli_rejects_dry_run_with_check(tmp_path: Path) -> None:
    source = tmp_path / "personal"

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--dry-run", "--check"])

    assert result.exit_code == 2
    assert "--dry-run cannot be combined with --check" in result.output


def test_cli_never_reads_the_old_agent_skills_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    source = tmp_path / "personal"
    make_skill(source, "portable")
    source_list = tmp_path / "home" / ".config" / "agent-skills" / "sources.d" / "personal"
    source_list.parent.mkdir(parents=True)
    source_list.write_text(f"{source}\n")

    result = CliRunner().invoke(cli, [])

    assert result.exit_code == 2
    assert "no skill sources configured" in result.output
    assert not (tmp_path / "home" / ".agents" / "skills").exists()


def test_cli_without_sources_names_the_braid_config_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    result = CliRunner().invoke(cli, [])

    assert result.exit_code == 2
    assert str(tmp_path / "home" / ".config" / "braid" / "sources.d") in result.output


def test_cli_reports_an_os_error_after_a_backup_and_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    (tmp_path / "home" / ".agents" / "skills" / "portable").mkdir(parents=True)

    def deny(*_args: object, **_kwargs: object) -> str:
        raise PermissionError("denied")

    monkeypatch.setattr("braid.domain.engine.create_directory_link", deny)

    result = CliRunner().invoke(cli, roots(tmp_path, source))

    assert result.exit_code == 2
    lines = result.output.splitlines()
    backup_index = next(index for index, line in enumerate(lines) if line.startswith("BACKUP "))
    failure_index = next(index for index, line in enumerate(lines) if "braid: denied" in line)
    assert backup_index < failure_index
    assert isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output


def test_cli_keeps_a_long_report_line_whole_at_80_columns(tmp_path: Path) -> None:
    source = tmp_path / ("x" * 90) / "personal"
    skill = make_skill(source, "portable")
    destination = tmp_path / "home" / ".agents" / "skills" / "portable"

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--no-claude", "--no-kiro"])

    assert result.exit_code == 0
    link_lines = [line for line in result.output.splitlines() if line.startswith("LINK[symlink] ")]
    assert len(link_lines) == 1
    assert str(destination) in link_lines[0]
    assert str(skill.resolve()) in link_lines[0]
