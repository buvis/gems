from __future__ import annotations

import json
import os
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from backup.cli import cli

if TYPE_CHECKING:
    from collections.abc import Callable


def _config(tmp_path: Path, instances: dict[str, dict[str, object]]) -> Path:
    path = tmp_path / "backup.yaml"
    isolated = {"git-src": {"use": "tar-archive", "enabled": False}, **instances}
    path.write_text(json.dumps({"instances": isolated}), encoding="utf-8")
    return path


def _instance(source: Path, out: Path, **fields: object) -> dict[str, object]:
    return {"use": "tar-archive", "with": {"source": str(source), "out": str(out)}, **fields}


@pytest.mark.parametrize("name", ["notes", "photos"])
@pytest.mark.parametrize("existing", [False, True])
def test_cli_plan_formats_run_and_skip_rows_and_preserves_existing_outputs(
    tmp_path: Path,
    name: str,
    existing: bool,
) -> None:
    source = tmp_path / name
    source.mkdir()
    missing = tmp_path / f"{name}-missing"
    out = tmp_path / f"{name}.tgz"
    missing_out = tmp_path / f"{name}-missing.tgz"
    if existing:
        out.write_bytes(b"original archive")
        missing_out.write_bytes(b"original missing-source archive")
    config = _config(
        tmp_path,
        {
            name: _instance(source, out),
            f"{name}-missing": _instance(missing, missing_out),
        },
    )
    suffix = "  [replaces existing]" if existing else ""

    with patch("backup.cli.console.info", autospec=True) as info:
        result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(config), "--plan"])

    assert result.exit_code == 0, result.output
    assert [call.args[0] for call in info.call_args_list] == [
        f"{name}  run  {source} -> {out}{suffix}",
        f"{name}-missing  skip  {missing} -> {missing_out}  (source not found: {missing}){suffix}",
    ]
    assert not missing.exists()
    assert out.exists() is existing
    assert missing_out.exists() is existing
    if existing:
        assert out.read_bytes() == b"original archive"
        assert missing_out.read_bytes() == b"original missing-source archive"


@pytest.mark.parametrize("failed_first", [False, True])
@pytest.mark.parametrize("name", ["records", "pictures"])
def test_cli_plan_prints_every_row_and_exits_one_for_invalid_items(
    tmp_path: Path,
    failed_first: bool,
    name: str,
) -> None:
    source = tmp_path / name
    source.mkdir()
    out = tmp_path / f"{name}.tgz"
    invalid = {"use": "tar-archive", "with": {"source": str(source), "out": str(out), "items": []}}
    good_out = tmp_path / f"{name}-good.tgz"
    entries = [(f"{name}-bad", invalid), (name, _instance(source, good_out))]
    if not failed_first:
        entries.reverse()
    for order, (_, instance) in enumerate(entries):
        instance["order"] = order
    config = _config(tmp_path, dict(entries))

    with patch("backup.cli.console.info", autospec=True) as info:
        result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(config), "--plan"])

    assert result.exit_code == 1, result.output
    expected = {
        f"{name}-bad": f"{name}-bad  fail  {source} -> {out}  (items must not be empty)",
        name: f"{name}  run  {source} -> {good_out}",
    }
    assert [call.args[0] for call in info.call_args_list] == [expected[label] for label, _ in entries]
    assert not out.exists()
    assert not good_out.exists()


@pytest.mark.parametrize("names", [("notes", "photos"), ("work", "music")])
@pytest.mark.parametrize("selector", ["only", "comma", "tag"])
def test_cli_plan_applies_exact_selection_to_all_requested_instances(
    tmp_path: Path,
    names: tuple[str, str],
    selector: str,
) -> None:
    instances = {}
    for name in (*names, f"{names[0]}-copy", f"copy-{names[1]}"):
        source = tmp_path / name
        source.mkdir()
        tag = "daily" if name in names else "daily-copy"
        instances[name] = _instance(source, tmp_path / f"{name}.tgz", tags=[tag])
    config = _config(tmp_path, instances)
    flags = {
        "only": ["--only", names[0], "--only", names[1]],
        "comma": ["--only", ",".join(names)],
        "tag": ["--tag", "daily"],
    }[selector]

    with patch("backup.cli.console.info", autospec=True) as info:
        result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(config), "--plan", *flags])

    assert result.exit_code == 0, result.output
    assert [call.args[0] for call in info.call_args_list] == [
        f"{name}  run  {tmp_path / name} -> {tmp_path / f'{name}.tgz'}" for name in sorted(names)
    ]
    assert not list(tmp_path.glob("*.tgz"))


@pytest.mark.parametrize("empty_config", [False, True])
def test_cli_plan_accepts_empty_selection_without_archive_effects(tmp_path: Path, empty_config: bool) -> None:
    source = tmp_path / "notes"
    source.mkdir()
    out = tmp_path / "notes.tgz"
    config = _config(tmp_path, {} if empty_config else {"notes": _instance(source, out, tags=["daily-copy"])})
    args = ["--config-dir", str(tmp_path), "--config", str(config), "--plan"]
    if not empty_config:
        args += ["--tag", "daily"]

    result = CliRunner().invoke(cli, args)

    assert result.exit_code == 0, result.output
    assert "  run  " not in result.output
    assert "  fail  " not in result.output
    assert not out.exists()


@pytest.mark.parametrize("name", ["alternate", "replacement"])
@pytest.mark.parametrize("override", ["source", "out", "both"])
def test_cli_plan_uses_source_and_out_overrides_for_the_selected_instance(
    tmp_path: Path,
    name: str,
    override: str,
) -> None:
    source = tmp_path / "configured"
    source.mkdir()
    alternate = tmp_path / name
    alternate.mkdir()
    out = tmp_path / "configured.tgz"
    alternate_out = tmp_path / f"{name}.tgz"
    alternate_out.write_bytes(b"preserve override destination")
    config = _config(
        tmp_path,
        {
            "selected": _instance(source, out),
            "selected-copy": _instance(source, tmp_path / "other.tgz"),
        },
    )
    args = ["--config-dir", str(tmp_path), "--config", str(config), "--plan", "--only", "selected"]
    if override in {"source", "both"}:
        args += ["--source", str(alternate)]
    if override in {"out", "both"}:
        args += ["--out", str(alternate_out)]
    expected_source = alternate if override in {"source", "both"} else source
    expected_out = alternate_out if override in {"out", "both"} else out
    suffix = "  [replaces existing]" if expected_out == alternate_out else ""

    with patch("backup.cli.console.info", autospec=True) as info:
        result = CliRunner().invoke(cli, args)

    assert result.exit_code == 0, result.output
    assert [call.args[0] for call in info.call_args_list] == [
        f"selected  run  {expected_source} -> {expected_out}{suffix}",
    ]
    assert alternate_out.read_bytes() == b"preserve override destination"
    assert not out.exists()


@pytest.mark.parametrize("count", [0, 2])
@pytest.mark.parametrize("flag", ["--source", "--out"])
def test_cli_plan_rejects_overrides_without_exactly_one_selected_instance(
    tmp_path: Path,
    count: int,
    flag: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    config = _config(
        tmp_path, {f"notes-{number}": _instance(source, tmp_path / f"notes-{number}.tgz") for number in range(count)}
    )

    result = CliRunner().invoke(
        cli, ["--config-dir", str(tmp_path), "--config", str(config), "--plan", flag, str(tmp_path / "override")]
    )

    assert result.exit_code == 1, result.output
    assert "exactly one selected instance" in result.output
    assert not (tmp_path / "override").exists()
    assert not list(tmp_path.glob("*.tgz"))


@pytest.mark.parametrize("flags", [["--plan", "--dry-run"], ["--dry-run", "--plan"]])
def test_cli_plan_rejects_dry_run_combination_without_writing(tmp_path: Path, flags: list[str]) -> None:
    source = tmp_path / "source"
    source.mkdir()
    out = tmp_path / "archive.tgz"
    out.write_bytes(b"preserve archive")
    config = _config(tmp_path, {"notes": _instance(source, out)})

    result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(config), *flags])

    assert result.exit_code == 1, result.output
    assert "--plan and --dry-run are mutually exclusive" in result.output
    assert out.read_bytes() == b"preserve archive"


@pytest.mark.parametrize("name", ["notes", "photos"])
def test_cli_dry_run_still_reports_selected_files_without_creating_archive(tmp_path: Path, name: str) -> None:
    source = tmp_path / name
    source.mkdir()
    (source / "first.txt").write_bytes(b"first")
    (source / "second.txt").write_bytes(b"second")
    out = tmp_path / f"{name}.tgz"
    config = _config(tmp_path, {name: _instance(source, out)})

    result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(config), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "2 files" in result.output
    assert not out.exists()
    assert (source / "first.txt").read_bytes() == b"first"
    assert (source / "second.txt").read_bytes() == b"second"


@pytest.mark.parametrize("names", [("notes", "notes-copy"), ("photos", "photos-copy")])
def test_cli_plan_surfaces_both_colliding_outputs_and_preserves_archive(
    tmp_path: Path,
    names: tuple[str, str],
) -> None:
    out = tmp_path / "shared.tgz"
    out.write_bytes(b"original archive")
    instances = {}
    for name in names:
        source = tmp_path / name
        source.mkdir()
        instances[name] = _instance(source, out)
    config = _config(tmp_path, instances)

    with patch("backup.cli.console.info", autospec=True) as info:
        result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(config), "--plan"])

    assert result.exit_code == 1, result.output
    assert [call.args[0] for call in info.call_args_list] == [
        f"{name}  fail  {tmp_path / name} -> {out}"
        f"  (output '{out}' is also the output of '{other}')  [replaces existing]"
        for name, other in (names, names[::-1])
    ]
    assert out.read_bytes() == b"original archive"


def _guard_source_walk(original: Callable[..., object], source: Path) -> Callable[..., object]:
    def guarded(path: object, *args: object, **kwargs: object) -> object:
        if isinstance(path, (str, bytes, os.PathLike)):
            candidate = Path(os.fsdecode(path))
            if candidate == source or source in candidate.parents:
                pytest.fail("--plan must not walk the source tree")
        return original(path, *args, **kwargs)

    return guarded


@pytest.mark.parametrize("name", ["notes", "photos"])
def test_cli_plan_reads_metadata_without_walking_or_creating_directories(tmp_path: Path, name: str) -> None:
    source = tmp_path / name
    source.mkdir()
    (source / "content.txt").write_bytes(b"unchanged")
    out = tmp_path / "uncreated" / f"{name}.tgz"
    config = _config(tmp_path, {name: _instance(source, out)})

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("--plan must not walk sources or write archives")

    with (
        patch.object(os, "walk", _guard_source_walk(os.walk, source)),
        patch.object(os, "scandir", _guard_source_walk(os.scandir, source)),
        patch.object(os, "replace", forbidden),
        patch.object(tarfile, "open", forbidden),
    ):
        result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(config), "--plan"])

    assert result.exit_code == 0, result.output
    assert not out.parent.exists()
    assert (source / "content.txt").read_bytes() == b"unchanged"
