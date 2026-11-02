from __future__ import annotations

import tarfile
from pathlib import Path

import pytest
import yaml
from buvis.pybase.result import FatalError

from backup.cli import cli
from backup.config import BackupConfig, BackupInstance, effective_excludes, load_config
from backup.runner import Runner


def _tree(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _config_file(root: Path, instances: dict[str, dict[str, object]], excludes: list[str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "buvis-backup.yaml"
    path.write_text(yaml.safe_dump({"instances": instances, "excludes": excludes}), encoding="utf-8")
    return path


def _archive_members(path: Path) -> set[str]:
    with tarfile.open(path, mode="r:gz") as archive:
        return {member.name for member in archive.getmembers() if member.isfile()}


class TestInstanceExcludeFields:
    def test_defaults_inherit_without_additions_or_removals(self) -> None:
        instance = BackupInstance.model_validate({"use": "tar-archive"})
        assert instance.inherit_excludes is True
        assert instance.exclude_add == ()
        assert instance.exclude_remove == ()

    @pytest.mark.parametrize("inherit", [True, False])
    def test_loads_instance_fields_beside_with(self, tmp_path: Path, inherit: bool) -> None:
        path = _config_file(
            tmp_path,
            {
                "documents": {
                    "use": "tar-archive",
                    "with": {"source": "/documents", "out": "/archive.tar.gz"},
                    "exclude_add": ["scratch", "sub/cache"],
                    "exclude_remove": ["target", "dist"],
                    "inherit_excludes": inherit,
                },
            },
            ["target", "dist", "node_modules"],
        )
        instance = load_config(config_dir=str(path.parent)).instances["documents"]
        assert instance.exclude_add == ("scratch", "sub/cache")
        assert instance.exclude_remove == ("target", "dist")
        assert instance.inherit_excludes is inherit
        assert instance.with_ == {"source": "/documents", "out": "/archive.tar.gz"}

    @pytest.mark.parametrize("key", ["exclude_ad", "exclude_remov"])
    def test_unknown_instance_key_raises_fatal(self, tmp_path: Path, key: str) -> None:
        path = _config_file(tmp_path, {"documents": {"use": "tar-archive", key: ["scratch"]}}, [])
        with pytest.raises(FatalError, match=key):
            load_config(config_dir=str(path.parent))

    @pytest.mark.parametrize("key", ["exclude_add", "exclude_remove", "inherit_excludes"])
    def test_exclude_fields_inside_with_are_rejected(self, tmp_path: Path, key: str) -> None:
        path = _config_file(tmp_path, {"documents": {"use": "tar-archive", "with": {key: []}}}, [])
        with pytest.raises(FatalError, match="unknown input"):
            load_config(config_dir=str(path.parent))


class TestEffectiveExcludes:
    @pytest.mark.parametrize(
        ("base", "fields", "expected"),
        [
            ([], {}, ()),
            (["target", "dist"], {}, ("target", "dist")),
            (["target", "dist"], {"inherit_excludes": False}, ()),
            (
                ["target", "target-notes", "sub/target", "dist", "target"],
                {"exclude_remove": ["target", "missing", "tar"], "exclude_add": ["scratch", "dist", "logs"]},
                ("target-notes", "sub/target", "dist", "scratch", "logs"),
            ),
            (
                ["target", "dist", "node_modules", "dist"],
                {"exclude_remove": ["target", "dist"], "exclude_add": ["dist", "scratch", "scratch", "target"]},
                ("node_modules", "dist", "scratch", "target"),
            ),
            (
                ["target", "dist"],
                {"inherit_excludes": False, "exclude_remove": ["scratch"], "exclude_add": ["scratch", "sub/cache"]},
                ("scratch", "sub/cache"),
            ),
            ([], {"exclude_add": ["logs", "cache", "logs"]}, ("logs", "cache")),
        ],
        ids=["empty", "defaults", "no-inheritance", "exact-removal", "readd-order", "only-additions", "empty-base"],
    )
    def test_effective_excludes_keep_first_occurrence_in_order(
        self, base: list[str], fields: dict[str, object], expected: tuple[str, ...]
    ) -> None:
        cfg = BackupConfig.model_validate({"excludes": base})
        instance = BackupInstance.model_validate({"use": "tar-archive", **fields})
        assert effective_excludes(cfg, instance) == expected


class TestRunnerInstanceExcludes:
    @pytest.mark.parametrize(
        ("fields", "kept"),
        [
            ({"exclude_add": ["scratch", "logs"]}, {"target-notes/x", "scratchpad/x", "catalogs/x"}),
            (
                {"exclude_remove": ["target", "missing"]},
                {"target/x", "scratch/x", "logs/x", "target-notes/x", "scratchpad/x", "catalogs/x"},
            ),
        ],
        ids=["add-to-inherited", "remove-exact-pattern"],
    )
    def test_runner_add_and_remove_affect_only_selected_instance(
        self, tmp_path: Path, fields: dict[str, object], kept: set[str]
    ) -> None:
        source = tmp_path / "src"
        files = {
            "target/x": "target",
            "node_modules/x": "dependency",
            "scratch/x": "scratch",
            "logs/x": "log",
            "target-notes/x": "notes",
            "scratchpad/x": "pad",
            "catalogs/x": "catalog",
        }
        _tree(source, files)
        adjusted_out, default_out = tmp_path / "adjusted.tar.gz", tmp_path / "default.tar.gz"
        cfg = BackupConfig.model_validate(
            {
                "excludes": ["target", "node_modules"],
                "instances": {
                    "adjusted": {
                        "use": "tar-archive",
                        "with": {"source": str(source), "out": str(adjusted_out)},
                        **fields,
                    },
                    "default": {"use": "tar-archive", "with": {"source": str(source), "out": str(default_out)}},
                },
            }
        )
        results = list(Runner(cfg).run(list(cfg.instances.items())))
        assert [step.success for step in results] == [True, True]
        assert sorted(step.label for step in results) == ["adjusted", "default"]
        assert _archive_members(adjusted_out) == {f"src/{path}" for path in kept}
        assert _archive_members(default_out) == {
            "src/scratch/x",
            "src/logs/x",
            "src/target-notes/x",
            "src/scratchpad/x",
            "src/catalogs/x",
        }

    @pytest.mark.parametrize(
        ("add", "additional_kept"),
        [
            ([], {"documents/sub/cache/drop", "documents/other/tmp/drop"}),
            (["sub/cache", "other/tmp"], set()),
        ],
        ids=["no-additions", "relative-additions"],
    )
    def test_inherit_false_keeps_build_dirs(self, tmp_path: Path, add: list[str], additional_kept: set[str]) -> None:
        source = tmp_path / "documents"
        _tree(
            source,
            {
                "build/first": "one",
                "nested/build/second": "two",
                "node_modules/keep": "three",
                "sub/cache/drop": "four",
                "other/tmp/drop": "five",
                "elsewhere/cache/keep": "six",
                "outer/sub/cache/keep": "seven",
                "sub/cache-notes/keep": "eight",
                "other/tmp-notes/keep": "nine",
            },
        )
        out = tmp_path / "documents.tar.gz"
        cfg = BackupConfig.model_validate(
            {
                "excludes": ["build", "node_modules"],
                "instances": {
                    "home": {
                        "use": "tar-archive",
                        "inherit_excludes": False,
                        "exclude_add": add,
                        "with": {"source": str(source), "out": str(out)},
                    }
                },
            }
        )
        results = list(Runner(cfg).run([("home", cfg.instances["home"])]))
        assert [step.success for step in results] == [True]
        expected = {
            "documents/build/first",
            "documents/nested/build/second",
            "documents/node_modules/keep",
            "documents/elsewhere/cache/keep",
            "documents/outer/sub/cache/keep",
            "documents/sub/cache-notes/keep",
            "documents/other/tmp-notes/keep",
        }
        assert _archive_members(out) == expected | additional_kept


class TestShowInstanceExcludes:
    @pytest.mark.parametrize(
        ("name", "fields", "expected", "removed", "directory"),
        [
            (
                "documents",
                {"exclude_remove": ["target"], "exclude_add": ["scratch", "logs"]},
                ["node_modules", "scratch", "logs"],
                ["target"],
                "target",
            ),
            (
                "config",
                {"inherit_excludes": False, "exclude_add": ["private-cache", "scratch"]},
                ["private-cache", "scratch"],
                ["target", "node_modules"],
                "node_modules",
            ),
        ],
        ids=["remove-global", "disable-inheritance"],
    )
    def test_show_excludes_prints_effective_list_and_resolves_bkpignore(
        self,
        runner,
        tmp_path: Path,
        name: str,
        fields: dict[str, object],
        expected: list[str],
        removed: list[str],
        directory: str,
    ) -> None:
        source = tmp_path / "source"
        _tree(source, {f"{directory}/.bkpignore": "local-rule\n!local-other\n", f"{directory}/keep": "keep"})
        out = tmp_path / "never-created.tar.gz"
        config = _config_file(
            tmp_path / "cfg",
            {
                name: {"use": "tar-archive", "with": {"source": str(source), "out": str(out)}, **fields},
                "unselected": {"use": "tar-archive", "exclude_add": ["other-instance-only"]},
            },
            ["target", "node_modules"],
        )
        result = runner.invoke(
            cli,
            [
                "--config-dir",
                str(config.parent),
                "--show-excludes",
                name,
                "--for",
                str(source / directory),
            ],
        )
        assert result.exit_code == 0, result.output
        assert f"resolved excludes for '{name}':" in result.output
        listed = result.output.split(".bkpignore rules effective under", 1)[0]
        assert all(pattern in listed for pattern in expected)
        assert all(pattern not in listed for pattern in removed)
        assert "other-instance-only" not in result.output
        assert "+local-rule" in result.output
        assert "!local-other" in result.output
        assert not out.exists()

    def test_show_excludes_prints_effective_list_sorted(self, runner, tmp_path: Path) -> None:
        config = _config_file(
            tmp_path,
            {"home": {"use": "tar-archive", "exclude_add": ["mid"]}},
            ["zeta", "alpha"],
        )
        result = runner.invoke(cli, ["--config-dir", str(config.parent), "--show-excludes", "home"])
        assert result.exit_code == 0, result.output
        lines = result.output.splitlines()
        start = next(i for i, line in enumerate(lines) if "resolved excludes for 'home':" in line) + 1
        end = next(i for i, line in enumerate(lines) if ".bkpignore rules omitted" in line)
        assert [line.strip() for line in lines[start:end]] == ["alpha", "mid", "zeta"]

    def test_show_excludes_accepts_empty_effective_list(self, runner, tmp_path: Path) -> None:
        config = _config_file(
            tmp_path,
            {
                "empty": {"use": "tar-archive", "inherit_excludes": False},
            },
            ["target", "dist"],
        )
        result = runner.invoke(cli, ["--config-dir", str(config.parent), "--show-excludes", "empty"])
        assert result.exit_code == 0, result.output
        assert "resolved excludes for 'empty':" in result.output
        assert "target" not in result.output
        assert "dist" not in result.output
        assert ".bkpignore rules omitted" in result.output
