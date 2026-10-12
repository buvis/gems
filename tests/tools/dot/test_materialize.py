from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from buvis.pybase.result import CommandResult
from dot.cli import cli
from dot.commands.materialize.materialize import CommandMaterialize
from dot.hostlinks import HOOK_NAMES, MANIFEST_PATH

SERVICE_PATH = "dot.commands.materialize.materialize.DotGitService"


def write_manifest(root: Path, *lines: str) -> None:
    manifest = root / MANIFEST_PATH
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("\n".join(lines) + "\n")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    dotroot = tmp_path / "dotroot"
    (dotroot / "hosts" / "h1" / "vim").mkdir(parents=True)
    (dotroot / "hosts" / "h1" / "bashrc").write_text("export A=1\n")
    write_manifest(dotroot, ".bashrc => hosts/h1/bashrc", ".vim => hosts/h1/vim")
    return dotroot


def git_service_returning(hooks_dir: Path | None) -> MagicMock:
    service = MagicMock()
    service.hooks_path.return_value = hooks_dir
    return service


class TestCommandMaterializeLinks:
    def test_creates_links_and_reports_them(self, root: Path) -> None:
        cmd = CommandMaterialize(MagicMock(), str(root), install_hooks=False)

        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is True
        assert (root / ".bashrc").is_symlink()
        assert (root / ".vim").is_symlink()
        assert (root / ".bashrc").resolve() == (root / "hosts/h1/bashrc").resolve()
        assert (root / ".vim").resolve() == (root / "hosts/h1/vim").resolve()
        assert "linked .bashrc" in result.info
        assert "linked .vim" in result.info
        assert result.warnings == []
        assert result.output is None

    def test_second_run_reports_nothing(self, root: Path) -> None:
        cmd = CommandMaterialize(MagicMock(), str(root), install_hooks=False)
        cmd.execute()

        result = cmd.execute()

        assert result.success is True
        assert result.info == []
        assert result.warnings == []

    def test_missing_source_is_a_warning_not_a_failure(self, root: Path) -> None:
        write_manifest(root, ".gone => hosts/h1/gone")

        result = CommandMaterialize(MagicMock(), str(root), install_hooks=False).execute()

        assert result.success is True
        assert result.warnings == [".gone: no host file at hosts/h1/gone"]
        assert not (root / ".gone").is_symlink()

    def test_no_manifest_yields_empty_success(self, tmp_path: Path) -> None:
        result = CommandMaterialize(MagicMock(), str(tmp_path), install_hooks=False).execute()

        assert result.success is True
        assert result.info == []
        assert result.warnings == []


class TestCommandMaterializeHookMode:
    def test_makes_no_shell_call_and_builds_no_git_service(self, root: Path, mocker) -> None:
        service_cls = mocker.patch(SERVICE_PATH)
        shell = MagicMock()

        result = CommandMaterialize(shell, str(root), install_hooks=False).execute()

        assert result.success is True
        assert "linked .bashrc" in result.info
        shell.exe.assert_not_called()
        service_cls.assert_not_called()

    def test_constructor_alone_does_not_touch_git(self, root: Path, mocker) -> None:
        service_cls = mocker.patch(SERVICE_PATH)
        shell = MagicMock()

        CommandMaterialize(shell, str(root))

        shell.exe.assert_not_called()
        service_cls.assert_not_called()


class TestCommandMaterializeHooks:
    def test_unset_hooks_path_installs_nothing(self, root: Path) -> None:
        service = git_service_returning(None)

        result = CommandMaterialize(MagicMock(), str(root), git_service=service).execute()

        assert result.success is True
        assert "linked .bashrc" in result.info
        assert not any(line.startswith("installed hook") for line in result.info)
        assert result.warnings == []
        created = {p.name for p in root.rglob("*")}
        assert not created & set(HOOK_NAMES)

    def test_installs_hooks_after_link_changes_in_order(self, root: Path, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        service = git_service_returning(hooks_dir)

        result = CommandMaterialize(MagicMock(), str(root), git_service=service).execute()

        assert result.success is True
        assert result.info[-len(HOOK_NAMES) :] == [f"installed hook {name}" for name in HOOK_NAMES]
        assert "linked .bashrc" in result.info[: -len(HOOK_NAMES)]
        for name in HOOK_NAMES:
            assert (hooks_dir / name).is_file()

    def test_already_installed_hooks_are_not_reported_again(self, root: Path, tmp_path: Path) -> None:
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        service = git_service_returning(hooks_dir)
        CommandMaterialize(MagicMock(), str(root), git_service=service).execute()

        result = CommandMaterialize(MagicMock(), str(root), git_service=service).execute()

        assert result.info == []
        assert result.warnings == []

    def test_install_oserror_becomes_hooks_warning(self, root: Path, tmp_path: Path) -> None:
        blocker = tmp_path / "blocker"
        blocker.write_text("i am a file")
        service = git_service_returning(blocker / "hooks")

        result = CommandMaterialize(MagicMock(), str(root), git_service=service).execute()

        assert result.success is True
        assert len(result.warnings) == 1
        assert result.warnings[0].startswith("hooks: ")
        assert "linked .bashrc" in result.info

    def test_link_problems_and_hook_installs_are_both_kept(self, root: Path, tmp_path: Path) -> None:
        write_manifest(root, ".bashrc => hosts/h1/bashrc", ".gone => hosts/h1/gone")
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        service = git_service_returning(hooks_dir)

        result = CommandMaterialize(MagicMock(), str(root), git_service=service).execute()

        assert result.warnings == [".gone: no host file at hosts/h1/gone"]
        assert result.info[-1] == f"installed hook {HOOK_NAMES[-1]}"

    def test_injected_git_service_replaces_constructed_one(self, root: Path, mocker) -> None:
        service_cls = mocker.patch(SERVICE_PATH)
        service = git_service_returning(None)

        CommandMaterialize(MagicMock(), str(root), git_service=service).execute()

        service.hooks_path.assert_called_once_with()
        service_cls.assert_not_called()


class TestMaterializeCli:
    @pytest.fixture(autouse=True)
    def _env(self, root: Path, tmp_path: Path, monkeypatch, mocker) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("DOTFILES_ROOT", str(root))
        service_cls = mocker.patch(SERVICE_PATH)
        service_cls.return_value.hooks_path.return_value = None
        self.service_cls = service_cls

    def test_creates_links_then_second_run_is_silent(self, runner, root: Path) -> None:
        first = runner.invoke(cli, ["materialize"])

        assert first.exit_code == 0
        assert (root / ".bashrc").is_symlink()
        assert (root / ".vim").is_symlink()
        assert "linked .bashrc" in first.output
        assert "linked .vim" in first.output

        second = runner.invoke(cli, ["materialize"])

        assert second.exit_code == 0
        assert second.output.strip() == ""

    def test_prints_problems_and_still_exits_zero(self, runner, root: Path) -> None:
        write_manifest(root, ".gone => hosts/h1/gone")

        result = runner.invoke(cli, ["materialize"])

        assert result.exit_code == 0
        assert ".gone: no host file at hosts/h1/gone" in result.output

    def test_hook_flag_exits_zero_on_invalid_manifest_line(self, runner, root: Path) -> None:
        write_manifest(root, "this line has no arrow", ".bashrc => hosts/h1/bashrc")

        result = runner.invoke(cli, ["materialize", "--hook"])

        assert result.exit_code == 0

    def test_hook_flag_never_builds_git_service(self, runner, root: Path) -> None:
        result = runner.invoke(cli, ["materialize", "--hook"])

        assert result.exit_code == 0
        assert (root / ".bashrc").is_symlink()
        self.service_cls.assert_not_called()

    def test_hook_flag_second_run_is_silent(self, runner) -> None:
        runner.invoke(cli, ["materialize", "--hook"])

        result = runner.invoke(cli, ["materialize", "--hook"])

        assert result.exit_code == 0
        assert result.output.strip() == ""
