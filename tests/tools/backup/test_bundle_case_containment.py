from __future__ import annotations

import os
import tarfile
from pathlib import Path

import pytest

from backup.capabilities.tar_archive import TarArchive


@pytest.fixture(params=["python-tarfile", "system-tar"])
def engine(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture(params=["run", "dry_run", "plan"])
def mode(request: pytest.FixtureRequest) -> str:
    return request.param


def _outcome(source: Path, out: Path, engine: str, mode: str, items: object) -> tuple[bool, str]:
    kwargs = {"label": "bundle", "source": str(source), "out": str(out), "engine": engine, "items": items}
    if mode == "plan":
        entry = TarArchive().plan(**kwargs)
        assert entry.status in {"run", "fail"}
        return entry.status == "run", entry.reason
    (result,) = list(TarArchive().run(**kwargs, dry_run=mode == "dry_run"))
    return result.success, result.message


def _snapshot(source: Path) -> dict[str, bytes | str | None]:
    return {
        str(path.relative_to(source)): (
            str(path.readlink()) if path.is_symlink() else path.read_bytes() if path.is_file() else None
        )
        for path in source.rglob("*")
    }


def _case_alias(directory: Path) -> Path:
    alias = directory.with_name(directory.name.swapcase())
    if not alias.exists() or not alias.samefile(directory):
        pytest.skip("case-alias containment requires a real case-insensitive filesystem")
    return alias


class TestBundleCaseContainment:
    @pytest.mark.parametrize("error", ["output identity permission denied", "archive metadata access denied"])
    def test_output_identity_permission_error_fails_without_replacing_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine: str, mode: str, error: str
    ) -> None:
        source = tmp_path.resolve() / "source"
        directory = source / "Config"
        directory.mkdir(parents=True)
        (directory / "settings").write_bytes(b"selected settings")
        (source / "other").write_bytes(b"also selected")
        sibling = source / "Config-backup"
        sibling.mkdir()
        out = sibling / "archive.tar.gz"
        out.write_bytes(error.encode())
        before = _snapshot(source)
        real_lstat = Path.lstat

        def denied_lstat(path: Path) -> os.stat_result:
            if path == out:
                raise PermissionError(error)
            return real_lstat(path)

        with monkeypatch.context() as patch:
            patch.setattr(Path, "lstat", denied_lstat)
            success, message = _outcome(source, out, engine, mode, ["Config", "other"])

        assert success is False
        assert error in message
        assert _snapshot(source) == before

    @pytest.mark.parametrize("selected", ["Config", "Profiles"])
    @pytest.mark.parametrize("out_rel", ["", "archive.tar.gz", "new/deep/archive.tar.gz"])
    def test_case_alias_of_selected_directory_rejects_output_without_changes(
        self, tmp_path: Path, engine: str, mode: str, selected: str, out_rel: str
    ) -> None:
        source = tmp_path / "source"
        directory = source / selected
        directory.mkdir(parents=True)
        (directory / "settings").write_bytes(b"selected settings")
        (source / "other").write_bytes(b"also selected")
        alias = _case_alias(directory)
        out = alias / out_rel if out_rel else alias
        if out_rel == "archive.tar.gz":
            out.write_bytes(b"previous archive")
        before = _snapshot(source)

        success, message = _outcome(source, out, engine, mode, ["other", selected])

        assert success is False
        assert "inside selected item" in message
        assert str(out) in message
        assert str(directory) in message
        assert _snapshot(source) == before

    @pytest.mark.parametrize("selected", ["Config", "Profiles"])
    def test_near_miss_sibling_allows_output_and_keeps_every_selected_item(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine: str, mode: str, selected: str
    ) -> None:
        source = tmp_path / "source"
        directory = source / selected
        directory.mkdir(parents=True)
        (directory / "settings").write_bytes(selected.encode())
        (source / "other").write_bytes(b"second item")
        sibling = source / f"{selected}-backup"
        sibling.mkdir()
        out = sibling / "archive.tar.gz"
        out.write_bytes(b"previous archive")
        before = _snapshot(source)
        monkeypatch.chdir(sibling)

        success, _ = _outcome(source, Path(out.name), engine, mode, [selected, "other"])

        assert success is True
        if mode == "run":
            with tarfile.open(out, "r:gz") as archive:
                assert set(archive.getnames()) == {selected, f"{selected}/settings", "other"}
                assert archive.extractfile(f"{selected}/settings").read() == selected.encode()
                assert archive.extractfile("other").read() == b"second item"
        else:
            assert _snapshot(source) == before

    @pytest.mark.parametrize("out_parent", ["target", "link"])
    def test_final_symlink_items_allow_output_in_target_without_archiving_target_contents(
        self, tmp_path: Path, engine: str, mode: str, out_parent: str
    ) -> None:
        source = tmp_path / "source"
        target = source / "target"
        target.mkdir(parents=True)
        (target / "private").write_bytes(b"do not archive")
        (source / "link").symlink_to("target", target_is_directory=True)
        (source / "broken").symlink_to("absent")
        (source / "other").write_bytes(b"keep")
        out = source / out_parent / "archive.tar.gz"
        out.write_bytes(b"previous archive")
        before = _snapshot(source)

        success, _ = _outcome(source, out, engine, mode, ["link", "broken", "other"])

        assert success is True
        assert (target / "private").read_bytes() == b"do not archive"
        assert (source / "link").readlink() == Path("target")
        if mode == "run":
            with tarfile.open(out, "r:gz") as archive:
                members = {member.name: member for member in archive.getmembers()}
                assert set(members) == {"link", "broken", "other"}
                assert members["link"].issym()
                assert members["link"].linkname == "target"
                assert members["broken"].issym()
                assert members["broken"].linkname == "absent"
                assert archive.extractfile("other").read() == b"keep"
        else:
            assert _snapshot(source) == before

    @pytest.mark.parametrize(
        ("items", "message"),
        [
            ([], "items must not be empty"),
            (["Config", "../escape"], "invalid item '../escape': must be a relative path inside the source"),
            (["Config", None], "items must be a list of relative paths"),
        ],
    )
    def test_invalid_items_take_precedence_over_output_containment(
        self, tmp_path: Path, engine: str, mode: str, items: object, message: str
    ) -> None:
        source = tmp_path / "source"
        directory = source / "Config"
        directory.mkdir(parents=True)
        out = directory / "archive.tar.gz"
        out.write_bytes(b"previous archive")
        before = _snapshot(source)

        success, reason = _outcome(source, out, engine, mode, items)

        assert success is False
        assert reason == message
        assert _snapshot(source) == before
