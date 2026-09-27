from __future__ import annotations

from unittest.mock import patch

import click

from backup.cli import cli
from backup.config import BackupConfig
from backup.step_result import StepResult


def _cfg(instances: dict[str, dict[str, object]]) -> BackupConfig:
    return BackupConfig.model_validate({"instances": instances})


class TestBackupCliShape:
    def test_cli_is_a_single_command_not_a_group(self) -> None:
        assert isinstance(cli, click.Command)
        assert not isinstance(cli, click.Group)

    def test_help_lists_filters(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--only" in result.output
        assert "--tag" in result.output
        assert "--list" in result.output
        assert "--dry-run" in result.output


class TestBackupCliRun:
    def test_runs_all_applicable_and_renders_via_console(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch(
                "backup.runner.Runner.run",
                return_value=iter([StepResult("git-src", True, "archived 3 files -> /x (99 bytes)")]),
            ),
        ):
            result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "archived 3 files" in result.output

    def test_only_narrows_selection(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}, "docs": {"use": "tar-archive"}})
        plan = [("git-src", cfg.instances["git-src"]), ("docs", cfg.instances["docs"])]
        captured: dict[str, object] = {}

        def _fake_run(self, selected):
            captured["selected"] = [n for n, _ in selected]
            return iter([])

        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch("backup.runner.Runner.run", _fake_run),
        ):
            result = runner.invoke(cli, ["--only", "docs"])
        assert result.exit_code == 0
        assert captured["selected"] == ["docs"]

    def test_tag_narrows_selection(self, runner) -> None:
        cfg = _cfg(
            {
                "git-src": {"use": "tar-archive", "tags": ["code"]},
                "docs": {"use": "tar-archive", "tags": ["nightly"]},
            },
        )
        plan = [("git-src", cfg.instances["git-src"]), ("docs", cfg.instances["docs"])]
        captured: dict[str, object] = {}

        def _fake_run(self, selected):
            captured["selected"] = [n for n, _ in selected]
            return iter([])

        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch("backup.runner.Runner.run", _fake_run),
        ):
            result = runner.invoke(cli, ["--tag", "nightly"])
        assert result.exit_code == 0
        assert captured["selected"] == ["docs"]

    def test_only_unknown_reports(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch("backup.runner.Runner.run", return_value=iter([])),
        ):
            result = runner.invoke(cli, ["--only", "nope"])
        # an unknown --only name now fails the run (was exit 0): a mistyped
        # selector must not let a scheduled backup silently do nothing.
        assert result.exit_code != 0
        assert "unknown instance 'nope'" in result.output


class TestBackupCliList:
    def test_list_prints_plan_and_runs_nothing(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive", "order": 10}})
        plan = [("git-src", cfg.instances["git-src"])]
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch("backup.runner.Runner.run") as mock_run,
        ):
            result = runner.invoke(cli, ["--list"])
        assert result.exit_code == 0
        assert "git-src" in result.output
        assert mock_run.call_count == 0

    def test_list_empty_plan(self, runner) -> None:
        cfg = _cfg({})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[]),
        ):
            result = runner.invoke(cli, ["--list"])
        assert result.exit_code == 0
        assert "no configured instances" in result.output


class TestBackupCliDryRun:
    def test_dry_run_passes_flag_to_runner(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        plan = [("git-src", cfg.instances["git-src"])]
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch("backup.runner.Runner.__init__", return_value=None) as mock_init,
            patch("backup.runner.Runner.run", return_value=iter([])),
        ):
            result = runner.invoke(cli, ["--dry-run"])
        assert result.exit_code == 0
        assert mock_init.call_args.kwargs.get("dry_run") is True


class TestBackupCliErrors:
    def test_config_fatal_error_panics_not_traceback(self, runner) -> None:
        from buvis.pybase.result import FatalError

        with patch("backup.config.load_config", side_effect=FatalError("bad config")):
            result = runner.invoke(cli, [])
        assert "bad config" in result.output
        assert "Traceback" not in result.output


class TestBackupCliExitCode:
    """FIX B: a failed step must make the process exit nonzero (cron must not
    treat an incomplete backup as success), while every step is still rendered."""

    def test_failing_step_exits_nonzero_but_renders_all(self, runner) -> None:
        cfg = _cfg({"a": {"use": "tar-archive"}, "b": {"use": "tar-archive"}})
        plan = [("a", cfg.instances["a"]), ("b", cfg.instances["b"])]
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch(
                "backup.runner.Runner.run",
                return_value=iter(
                    [
                        StepResult("a", False, "a failed: source not found"),
                        StepResult("b", True, "archived 2 files -> /x"),
                    ],
                ),
            ),
        ):
            result = runner.invoke(cli, [])
        assert result.exit_code != 0
        # both steps rendered — the failure did not short-circuit the success line
        assert "a failed" in result.output
        assert "archived 2 files" in result.output

    def test_all_success_exits_zero(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch(
                "backup.runner.Runner.run",
                return_value=iter([StepResult("git-src", True, "archived 3 files -> /x")]),
            ),
        ):
            result = runner.invoke(cli, [])
        assert result.exit_code == 0


class TestBackupCliForGuard:
    """FIX H: --for is meaningful only with --show-excludes; alone it must not
    run a backup and must report the misuse."""

    def test_for_without_show_excludes_does_not_run_and_reports(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch("backup.runner.Runner.run") as mock_run,
        ):
            result = runner.invoke(cli, ["--for", "/some/path"])
        assert result.exit_code != 0
        assert "--for requires --show-excludes" in result.output
        assert mock_run.call_count == 0

    def test_show_excludes_with_for_still_works(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive", "with": {"source": "/x", "out": "/o.tgz"}}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.runner.Runner.run") as mock_run,
        ):
            result = runner.invoke(cli, ["--show-excludes", "git-src", "--for", "/x/sub"])
        assert result.exit_code == 0
        assert "--for requires --show-excludes" not in result.output
        assert mock_run.call_count == 0


class TestShowExcludesExitCode:
    """A terminal validation failure in --show-excludes must exit nonzero, so a
    typo is distinguishable from a successful inspection to a script."""

    def test_unknown_instance_exits_nonzero(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with patch("backup.config.load_config", return_value=cfg):
            result = runner.invoke(cli, ["--show-excludes", "typo"])
        assert result.exit_code != 0
        assert "unknown instance 'typo'" in result.output

    def test_instance_without_source_exits_nonzero(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})  # no with.source
        with patch("backup.config.load_config", return_value=cfg):
            result = runner.invoke(cli, ["--show-excludes", "git-src", "--for", "/x"])
        assert result.exit_code != 0
        assert "no source configured" in result.output

    def test_known_instance_exits_zero(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with patch("backup.config.load_config", return_value=cfg):
            result = runner.invoke(cli, ["--show-excludes", "git-src"])
        assert result.exit_code == 0


class TestOnlyUnknownExitCode:
    """An unknown --only name (typo) must fail the run, so a scheduled backup
    can't silently do nothing (or less) after a mistyped selector."""

    def test_all_unknown_only_exits_nonzero_and_runs_nothing(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch("backup.runner.Runner.run", return_value=iter([])) as mock_run,
        ):
            result = runner.invoke(cli, ["--only", "typo"])
        assert result.exit_code != 0
        assert "unknown instance 'typo'" in result.output
        # empty plan -> Runner.run gets an empty list, produces no steps
        assert mock_run.call_count == 1

    def test_partial_unknown_only_still_runs_valid_but_exits_nonzero(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        plan = [("git-src", cfg.instances["git-src"])]
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch("backup.runner.Runner.run", return_value=iter([StepResult("git-src", True, "archived 1 -> /x")])),
        ):
            result = runner.invoke(cli, ["--only", "git-src,typo"])
        assert result.exit_code != 0
        assert "archived 1" in result.output  # valid one still ran
        assert "unknown instance 'typo'" in result.output

    def test_list_with_unknown_only_exits_nonzero(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        plan = [("git-src", cfg.instances["git-src"])]
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
        ):
            result = runner.invoke(cli, ["--list", "--only", "typo"])
        assert result.exit_code != 0


class TestBackupConfigSelectionThreaded:
    """`backup --config FILE` / `--config-dir DIR` load the PLAN from that selection (PRD 00084).

    These drive the REAL load_config (not the patched stub the other tests use)
    so the ctx.obj -> load_config -> find_config_files_ranked threading is
    exercised end to end. Discovery is isolated via BUVIS_CONFIG_DIR + HOME so
    the ambient environment cannot leak a real user config into the assertion.
    """

    def _isolate(self, tmp_path, monkeypatch) -> None:
        # Point discovery at an EMPTY dir and a fake HOME with no cwd config, so
        # only the bundled default + our explicit selection contribute.
        empty = tmp_path / "empty-config-dir"
        empty.mkdir()
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(empty))
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))
        monkeypatch.chdir(tmp_path / "empty-config-dir")

    def test_config_file_supplies_the_plan(self, runner, tmp_path, monkeypatch) -> None:
        """--config FILE introduces an instance the default plan does not have."""
        self._isolate(tmp_path, monkeypatch)
        cfg_file = tmp_path / "override.yaml"
        cfg_file.write_text(
            "instances:\n"
            "  fixture-only:\n"
            "    use: tar-archive\n"
            "    order: 5\n"
            "    with:\n"
            "      source: /tmp/x\n"
            "      out: /tmp/x.tar.gz\n"
        )

        result = runner.invoke(cli, ["--config", str(cfg_file), "--list"])

        assert result.exit_code == 0, result.output
        # The fixture's instance is present — only the explicit file could add it.
        assert "fixture-only" in result.output

    def test_config_file_hides_discovered_user_config(self, runner, tmp_path, monkeypatch) -> None:
        """--config FILE is EXCLUSIVE of DISCOVERED user files: a buvis-backup.yaml in the
        config dir must NOT merge under an explicit --config, or settings (FILE-only) and
        the plan would diverge — the settings/plan split review #181 flagged. The bundled
        default baseline still applies (that is the zero-config design, not a discovered file).
        """
        empty = tmp_path / "cfgdir"
        empty.mkdir()
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(empty))
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))
        monkeypatch.chdir(empty)
        # A DISCOVERED user config with its own instance — would leak in under the
        # old append semantics; must not, now that config_path is exclusive.
        (empty / "buvis-backup.yaml").write_text(
            "instances:\n"
            "  discovered-leak:\n"
            "    use: tar-archive\n"
            "    order: 8\n"
            "    with:\n"
            "      source: /tmp/z\n"
            "      out: /tmp/z.tar.gz\n"
        )
        cfg_file = tmp_path / "override.yaml"
        cfg_file.write_text(
            "instances:\n"
            "  fixture-only:\n"
            "    use: tar-archive\n"
            "    order: 5\n"
            "    with:\n"
            "      source: /tmp/x\n"
            "      out: /tmp/x.tar.gz\n"
        )

        result = runner.invoke(cli, ["--config", str(cfg_file), "--list"])

        assert result.exit_code == 0, result.output
        assert "fixture-only" in result.output
        # The discovered user config does NOT contribute under --config FILE.
        assert "discovered-leak" not in result.output

    def test_config_dir_supplies_the_plan(self, runner, tmp_path, monkeypatch) -> None:
        """--config-dir DIR discovers a buvis-backup.yaml with a distinct instance."""
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))
        monkeypatch.chdir(tmp_path)
        cfg_dir = tmp_path / "cfgdir"
        cfg_dir.mkdir()
        (cfg_dir / "buvis-backup.yaml").write_text(
            "instances:\n"
            "  from-dir:\n"
            "    use: tar-archive\n"
            "    order: 7\n"
            "    with:\n"
            "      source: /tmp/y\n"
            "      out: /tmp/y.tar.gz\n"
        )

        result = runner.invoke(cli, ["--config-dir", str(cfg_dir), "--list"])

        assert result.exit_code == 0, result.output
        assert "from-dir" in result.output

    def test_no_selection_uses_default_plan(self, runner, tmp_path, monkeypatch) -> None:
        """Without --config/--config-dir the bundled default plan (git-src) is used."""
        self._isolate(tmp_path, monkeypatch)

        result = runner.invoke(cli, ["--list"])

        assert result.exit_code == 0, result.output
        assert "git-src" in result.output
        assert "fixture-only" not in result.output
