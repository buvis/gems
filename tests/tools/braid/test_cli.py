from __future__ import annotations

import errno
import os
from pathlib import Path

import braid.cli as braid_cli
import pytest
from braid.cli import cli
from click.testing import CliRunner
from rich.console import Console

from tests.tools.braid.helpers import kiro_root, make_skill, read_state, settings, write_agent


@pytest.fixture(autouse=True)
def narrow_console(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(braid_cli.console, "console", Console(width=80, color_system=None))


def roots(tmp_path: Path, source: Path) -> list[str]:
    return [
        "--agents-root",
        str(tmp_path / "home" / ".agents"),
        "--claude-root",
        str(tmp_path / "home" / ".claude"),
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
    assert result.output.splitlines()[-1] == (
        "braid: 3 linked, 0 generated, 0 current, 1 ignored, 0 removed, 0 backed up, 0 configured, 0 unmanaged, "
        "3 change(s)"
    )
    assert (agents_root / "skills" / "machine-ignored").is_symlink()
    assert not os.path.lexists(claude_root / "skills" / "machine-ignored")


def test_cli_dry_run_reports_changes_without_writing(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    agents_root = tmp_path / "home" / ".agents"

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--dry-run"])

    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[-1] == (
        "braid: 0 linked, 0 generated, 0 current, 0 ignored, 0 removed, 0 backed up, 0 configured, 0 unmanaged, "
        "2 change(s)"
    )
    assert sum(line.startswith("WOULD LINK ") for line in lines) == 2
    assert not os.path.lexists(agents_root / "skills" / "portable")
    assert not os.path.lexists(tmp_path / "home" / ".claude" / "skills" / "portable")
    assert not os.path.lexists(agents_root / ".braid-state.json")


def buvis_config_dir() -> Path:
    """The BUVIS_CONFIG_DIR the autouse conftest fixture points at a scratch directory."""
    return Path(os.environ["BUVIS_CONFIG_DIR"])


def write_sources(config_dir: Path, *sources: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"  - {source}" for source in sources)
    (config_dir / "buvis-braid.yaml").write_text(f"sources:\n{lines}\n")


def root_flags(base: Path) -> list[str]:
    return [
        "--agents-root",
        str(base / ".agents"),
        "--claude-root",
        str(base / ".claude"),
    ]


def test_cli_projects_into_root_flags_outside_home(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    other = tmp_path / "other"
    write_sources(buvis_config_dir(), source)

    result = CliRunner().invoke(cli, root_flags(other))

    assert result.exit_code == 0
    assert (other / ".agents" / "skills" / "portable").is_symlink()
    assert (other / ".claude" / "skills" / "portable").is_symlink()
    assert (other / ".agents" / ".braid-state.json").is_file()
    assert not os.path.lexists(tmp_path / "home" / ".agents")
    assert not os.path.lexists(tmp_path / "home" / ".claude")


def test_cli_root_flags_win_over_the_environment_and_keep_yaml_and_flag_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "personal"
    make_skill(configured, "portable")
    extra = tmp_path / "extra"
    make_skill(extra, "extra-skill")
    env_root, flag_root = tmp_path / "env", tmp_path / "flag"
    write_sources(buvis_config_dir(), configured)
    monkeypatch.setenv("BUVIS_BRAID_AGENTS_ROOT", str(env_root / ".agents"))
    monkeypatch.setenv("BUVIS_BRAID_CLAUDE_ROOT", str(env_root / ".claude"))

    result = CliRunner().invoke(cli, [*root_flags(flag_root), "--source", str(extra)])

    assert result.exit_code == 0
    for name in ("portable", "extra-skill"):
        assert (flag_root / ".agents" / "skills" / name).is_symlink()
        assert (flag_root / ".claude" / "skills" / name).is_symlink()
    assert not os.path.lexists(env_root / ".agents")
    assert not os.path.lexists(env_root / ".claude")


def test_cli_policies_from_buvis_braid_yaml_keep_the_skill_out_of_claude(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    make_skill(source, "kept")
    policy = tmp_path / "yaml-policy"
    policy.write_text("portable\n")
    config_dir = buvis_config_dir()
    (config_dir / "buvis-braid.yaml").write_text(f"sources:\n  - {source}\npolicies:\n  - {policy}\n")
    home = tmp_path / "home"

    result = CliRunner().invoke(cli, root_flags(home))

    assert result.exit_code == 0
    assert ", 1 ignored, " in result.output.splitlines()[-1]
    assert (home / ".agents" / "skills" / "portable").is_symlink()
    assert not os.path.lexists(home / ".claude" / "skills" / "portable")
    assert (home / ".claude" / "skills" / "kept").is_symlink()


def test_cli_policy_flag_keeps_the_skill_out_of_claude(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    policy = tmp_path / "extra-policy"
    policy.write_text("portable\n")

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--policy", str(policy)])

    assert result.exit_code == 0
    assert result.output.splitlines()[-1] == (
        "braid: 1 linked, 0 generated, 0 current, 1 ignored, 0 removed, 0 backed up, 0 configured, 0 unmanaged, "
        "1 change(s)"
    )
    assert (tmp_path / "home" / ".agents" / "skills" / "portable").is_symlink()
    assert not os.path.lexists(tmp_path / "home" / ".claude" / "skills" / "portable")


def test_parser_documents_previously_bare_options_with_help_text() -> None:
    named_options = ("--policy", "--agents-root", "--claude-root", "--no-claude")

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
    assert result.output.splitlines()[-1] == (
        "braid: 3 linked, 0 generated, 0 current, 0 ignored, 0 removed, 1 backed up, 1 configured, 0 unmanaged, "
        "4 change(s)"
    )
    assert (kiro_root(plain) / "skills" / "portable").is_symlink()
    assert runner.invoke(cli, [*roots(tmp_path, source), "--check"]).exit_code == 0


def test_cli_kiro_flag_enrolls_the_default_kiro_root(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    kiro_root(plain).mkdir(parents=True)

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--kiro"])

    assert result.exit_code == 0
    assert (kiro_root(plain) / "skills" / "portable").is_symlink()
    assert read_state(plain)["kiro"]["agents"] == []


def test_cli_forget_kiro_agent_drops_it_from_the_saved_state(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    write_agent(plain, "dev", {"resources": []})
    runner = CliRunner()
    runner.invoke(cli, [*roots(tmp_path, source), "--kiro-root", str(kiro_root(plain)), "--kiro-agent", "dev"])
    assert read_state(plain)["kiro"]["agents"] == ["dev"]

    result = runner.invoke(cli, [*roots(tmp_path, source), "--forget-kiro-agent", "dev"])

    assert result.exit_code == 0
    assert result.output.splitlines()[-1] == (
        "braid: 0 linked, 0 generated, 3 current, 0 ignored, 0 removed, 0 backed up, 0 configured, 0 unmanaged, "
        "1 change(s)"
    )
    assert read_state(plain)["kiro"]["agents"] == []


def test_cli_enrolls_kiro_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    monkeypatch.setenv("BUVIS_BRAID_KIRO_ROOT", str(kiro_root(plain)))

    CliRunner().invoke(cli, roots(tmp_path, source))

    assert (kiro_root(plain) / "skills" / "portable").is_symlink()


def test_cli_kiro_root_flag_wins_over_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    env_kiro, flag_kiro = tmp_path / "env-kiro", tmp_path / "flag-kiro"
    env_kiro.mkdir()
    flag_kiro.mkdir()
    monkeypatch.setenv("BUVIS_BRAID_KIRO_ROOT", str(env_kiro))

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--kiro-root", str(flag_kiro)])

    assert result.exit_code == 0
    assert (flag_kiro / "skills" / "portable").is_symlink()
    assert list(env_kiro.iterdir()) == []


def test_cli_treats_an_empty_kiro_root_variable_as_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    monkeypatch.setenv("BUVIS_BRAID_KIRO_ROOT", "")

    result = CliRunner().invoke(cli, roots(tmp_path, source))

    assert result.exit_code == 0
    assert not os.path.lexists(tmp_path / "skills")
    assert "kiro" not in read_state(settings(tmp_path, source))


@pytest.mark.parametrize(
    "enrollment",
    [["--kiro"], ["--kiro-root", "X"], ["--kiro-agent", "dev"], ["--forget-kiro-agent", "dev"]],
)
def test_cli_rejects_no_kiro_combined_with_enrollment(tmp_path: Path, enrollment: list[str]) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--no-kiro", *enrollment])

    assert result.exit_code == 2
    assert "--no-kiro cannot be combined with Kiro enrollment options" in result.output
    assert not os.path.lexists(tmp_path / "home" / ".agents")


def test_cli_no_kiro_leaves_an_enrolled_kiro_root_untouched(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    plain = settings(tmp_path, source)
    kiro_link = kiro_root(plain) / "skills" / "portable"
    kiro_root(plain).mkdir(parents=True)
    runner = CliRunner()
    runner.invoke(cli, [*roots(tmp_path, source), "--kiro-root", str(kiro_root(plain))])
    assert kiro_link.is_symlink()
    kiro_link.unlink()

    result = runner.invoke(cli, [*roots(tmp_path, source), "--no-kiro"])

    assert result.exit_code == 0
    assert result.output.splitlines()[-1] == (
        "braid: 0 linked, 0 generated, 2 current, 0 ignored, 0 removed, 0 backed up, 0 configured, 0 unmanaged, "
        "0 change(s)"
    )
    assert not os.path.lexists(kiro_link)
    assert "kiro" in read_state(plain)


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


@pytest.mark.parametrize(
    "relative",
    ["personal/skills/portable/SKILL.md", "home/.agents/.braidignore"],
    ids=["skill", "braidignore"],
)
def test_cli_reports_a_non_utf8_input_file_on_one_line_and_exits_2(tmp_path: Path, relative: str) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    bad_file = tmp_path / relative
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_bytes(b"\xff\xfe\x00")

    result = CliRunner().invoke(cli, [*roots(tmp_path, source), "--no-kiro"])

    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)
    assert_one_error_line(result.output, f"braid: cannot read {bad_file}: ", "codec can't decode")


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


def test_cli_without_sources_names_buvis_braid_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    result = CliRunner().invoke(cli, [])

    assert result.exit_code == 2
    assert (
        "no skill sources configured; add a path to sources in ~/.config/buvis/buvis-braid.yaml or pass --source"
    ) in result.output
    assert not os.path.lexists(tmp_path / "home" / ".agents" / "skills")


def test_cli_help_does_not_offer_config_root() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "--source" in result.output
    assert "--config-root" not in result.output


def test_cli_check_passes_with_only_buvis_braid_yaml(tmp_path: Path) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    write_sources(buvis_config_dir(), source)
    runner = CliRunner()

    sync = runner.invoke(cli, [])
    check = runner.invoke(cli, ["--check"])

    assert sync.exit_code == 0
    assert (tmp_path / "home" / ".agents" / "skills" / "portable").is_symlink()
    assert (tmp_path / "home" / ".claude" / "skills" / "portable").is_symlink()
    assert check.exit_code == 0


def test_machine_local_sources_append_to_shared_buvis_braid_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BUVIS_CONFIG_DIR", raising=False)
    home = tmp_path / "isolated-home"
    monkeypatch.setenv("HOME", str(home))
    shared, local = tmp_path / "shared", tmp_path / "local"
    make_skill(shared, "shared-skill")
    make_skill(local, "local-skill")
    shared_config = home / ".config" / "buvis"
    shared_config.mkdir(parents=True)
    (shared_config / "buvis-braid.yaml").write_text(f"sources:\n  - {shared}\n")
    local_config = home / ".local" / ".config" / "buvis"
    local_config.mkdir(parents=True)
    (local_config / "buvis-braid.yaml").write_text(f"sources+:\n  - {local}\n")

    result = CliRunner().invoke(cli, [])

    assert result.exit_code == 0
    assert (home / ".agents" / "skills" / "shared-skill").is_symlink()
    assert (home / ".agents" / "skills" / "local-skill").is_symlink()


def test_cli_reports_an_os_error_after_a_backup_and_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "personal"
    make_skill(source, "portable")
    (tmp_path / "home" / ".agents" / "skills" / "portable").mkdir(parents=True)

    def fill_disk(*_args: object, **_kwargs: object) -> str:
        raise OSError(errno.ENOSPC, "no space")

    monkeypatch.setattr("braid.domain.engine.create_directory_link", fill_disk)

    result = CliRunner().invoke(cli, roots(tmp_path, source))

    assert result.exit_code == 2
    lines = result.output.splitlines()
    backup_index = next(index for index, line in enumerate(lines) if line.startswith("BACKUP "))
    failure_index = next(index for index, line in enumerate(lines) if "braid: [Errno 28] no space" in line)
    assert backup_index < failure_index
    assert_one_error_line(result.output, "braid: [Errno 28] no space", "no space")
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
