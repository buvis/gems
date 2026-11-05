"""File-link projections and the Windows hard-link fallback in the engine (PRD 00116)."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from braid.domain import engine
from braid.domain.engine import BraidError, Mode
from braid.domain.model import Result

from tests.tools.braid.helpers import make_rule


def deny_file_symlinks(monkeypatch: pytest.MonkeyPatch, code: int | None = 1314) -> None:
    """Simulate Windows without Developer Mode: file symlinks fail, directory symlinks work."""
    real_symlink = os.symlink

    def symlink(src: str, dst: str, target_is_directory: bool = False, **kwargs: object) -> None:
        if Path(src).is_file():
            error = OSError(code or 1, "denied")
            error.winerror = code
            raise error
        real_symlink(src, dst, target_is_directory, **kwargs)

    monkeypatch.setattr(os, "symlink", symlink)


def rule_file(tmp_path: Path, name: str, body: str) -> Path:
    return make_rule(tmp_path / "source", name, body) / "RULE.md"


def projection(
    tmp_path: Path,
    desired: dict[str, Path],
    previous: dict[str, str] | None = None,
    *,
    entry_suffix: str = ".md",
    file_links: bool = True,
) -> engine._Projection:
    destination_root = tmp_path / "home" / ".claude" / "rules"
    destination_root.mkdir(parents=True, exist_ok=True)
    return engine._Projection(
        desired=desired,
        previous=previous or {},
        destination_root=destination_root,
        backup_root=tmp_path / "backups",
        backup_category="rules",
        preserve_real_sources=False,
        entry_suffix=entry_suffix,
        file_links=file_links,
    )


def a_pass(mode: Mode, platform: str, emitted: list[str]) -> engine._Pass:
    return engine._Pass(mode, platform, Result(), emitted.append)


def rewrite(target: Path, body: str) -> None:
    """Replace the file the way an editor does: a new inode under the same name."""
    fresh = target.with_name("RULE.md.new")
    fresh.write_text(body, encoding="utf-8")
    os.replace(fresh, target)


def backed_up_bodies(tmp_path: Path) -> list[str]:
    root = tmp_path / "backups"
    if not root.exists():
        return []
    return [path.read_text(encoding="utf-8") for path in root.rglob("*") if path.is_file()]


def test_create_file_link_is_exported() -> None:
    assert "create_file_link" in engine.__all__


def test_create_file_link_prefers_a_symlink(tmp_path: Path) -> None:
    target = rule_file(tmp_path, "alpha", "alpha body")
    destination = tmp_path / "alpha.md"

    backend = engine.create_file_link(destination, target, platform="nt")

    assert backend == "symlink"
    assert destination.is_symlink()
    assert Path(os.readlink(destination)) == target


@pytest.mark.parametrize("code", [5, 1314])
def test_windows_file_link_falls_back_to_a_hard_link_on_privilege_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    target = rule_file(tmp_path, "alpha", "alpha body")
    destination = tmp_path / "alpha.md"
    deny_file_symlinks(monkeypatch, code)

    backend = engine.create_file_link(destination, target, platform="nt")

    assert backend == "hardlink"
    assert not destination.is_symlink()
    assert os.path.samefile(destination, target)


@pytest.mark.parametrize(("platform", "code"), [("nt", 2), ("nt", 1315), ("nt", None), ("posix", 1314)])
def test_symlink_failure_without_the_windows_privilege_gate_is_a_braid_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str, code: int | None
) -> None:
    target = rule_file(tmp_path, "alpha", "alpha body")
    destination = tmp_path / "alpha.md"
    deny_file_symlinks(monkeypatch, code)
    linked: list[tuple[str, ...]] = []

    with pytest.raises(BraidError, match=f"cannot link {re.escape(str(destination))} -> "):
        engine.create_file_link(destination, target, platform=platform, hard_link=lambda *args: linked.append(args))

    assert linked == []
    assert not os.path.lexists(destination)


def test_hard_link_receives_the_target_then_the_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = rule_file(tmp_path, "beta", "beta body")
    destination = tmp_path / "elsewhere" / "beta.md"
    deny_file_symlinks(monkeypatch)
    linked: list[tuple[str, ...]] = []

    backend = engine.create_file_link(destination, target, platform="nt", hard_link=lambda *args: linked.append(args))

    assert backend == "hardlink"
    assert linked == [(str(target), str(destination))]


def test_a_failing_hard_link_is_a_braid_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = rule_file(tmp_path, "alpha", "alpha body")
    destination = tmp_path / "alpha.md"
    deny_file_symlinks(monkeypatch)

    def cross_device(_src: str, _dst: str) -> None:
        raise OSError(18, "cross-device link")

    with pytest.raises(BraidError, match=f"cannot create hard link {re.escape(str(destination))} -> .*cross-device"):
        engine.create_file_link(destination, target, platform="nt", hard_link=cross_device)


@pytest.mark.parametrize("entry_suffix", [".md", ""])
def test_file_links_land_at_the_suffixed_name_and_state_keeps_the_bare_name(tmp_path: Path, entry_suffix: str) -> None:
    alpha = rule_file(tmp_path, "alpha", "alpha body")
    beta = rule_file(tmp_path, "alpha-beta", "beta body")
    project = projection(tmp_path, {"alpha": alpha, "alpha-beta": beta}, entry_suffix=entry_suffix)
    emitted: list[str] = []

    state = engine._sync_links(project, a_pass(Mode.SYNC, "posix", emitted))

    root = project.destination_root
    assert set(state) == {"alpha", "alpha-beta"}
    assert sorted(path.name for path in root.iterdir()) == [f"alpha{entry_suffix}", f"alpha-beta{entry_suffix}"]
    assert Path(os.readlink(root / f"alpha{entry_suffix}")) == alpha
    assert Path(os.readlink(root / f"alpha-beta{entry_suffix}")) == beta
    assert f"LINK[symlink] {root / f'alpha{entry_suffix}'} -> {alpha}" in emitted
    assert f"LINK[symlink] {root / f'alpha-beta{entry_suffix}'} -> {beta}" in emitted


def test_an_empty_file_link_projection_links_nothing(tmp_path: Path) -> None:
    project = projection(tmp_path, {})
    emitted: list[str] = []

    state = engine._sync_links(project, a_pass(Mode.SYNC, "nt", emitted))

    assert state == {}
    assert list(project.destination_root.iterdir()) == []
    assert not any(line.startswith("LINK") for line in emitted)


def test_windows_sync_reports_hard_links_and_a_second_pass_counts_them_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = rule_file(tmp_path, "alpha", "alpha body")
    beta = rule_file(tmp_path, "beta", "beta body")
    deny_file_symlinks(monkeypatch)
    root = tmp_path / "home" / ".claude" / "rules"
    first: list[str] = []
    state = engine._sync_links(projection(tmp_path, {"alpha": alpha, "beta": beta}), a_pass(Mode.SYNC, "nt", first))
    inodes = {name: (root / f"{name}.md").stat().st_ino for name in ("alpha", "beta")}
    second: list[str] = []
    run_pass = a_pass(Mode.SYNC, "nt", second)

    engine._sync_links(projection(tmp_path, {"alpha": alpha, "beta": beta}, state), run_pass)

    assert f"LINK[hardlink] {root / 'alpha.md'} -> {alpha}" in first
    assert f"LINK[hardlink] {root / 'beta.md'} -> {beta}" in first
    assert run_pass.result.current == 2
    assert run_pass.result.drift == 0
    assert not any(line.startswith(("LINK", "BACKUP")) for line in second)
    assert {name: (root / f"{name}.md").stat().st_ino for name in ("alpha", "beta")} == inodes


def test_a_symlink_failure_on_a_non_windows_pass_stops_the_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = rule_file(tmp_path, "alpha", "alpha body")
    deny_file_symlinks(monkeypatch)

    with pytest.raises(BraidError, match="cannot link"):
        engine._sync_links(projection(tmp_path, {"alpha": alpha}), a_pass(Mode.SYNC, "posix", []))

    assert not os.path.lexists(tmp_path / "home" / ".claude" / "rules" / "alpha.md")


def test_sync_backs_up_and_relinks_a_hard_link_whose_target_was_rewritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = rule_file(tmp_path, "alpha", "old body")
    deny_file_symlinks(monkeypatch)
    state = engine._sync_links(projection(tmp_path, {"alpha": alpha}), a_pass(Mode.SYNC, "nt", []))
    rewrite(alpha, "new body")
    destination = tmp_path / "home" / ".claude" / "rules" / "alpha.md"
    emitted: list[str] = []
    run_pass = a_pass(Mode.SYNC, "nt", emitted)

    engine._sync_links(projection(tmp_path, {"alpha": alpha}, state), run_pass)

    assert run_pass.result.drift >= 1
    assert os.path.samefile(destination, alpha)
    assert destination.read_text(encoding="utf-8") == "new body"
    assert backed_up_bodies(tmp_path) == ["old body"]
    backup = next(i for i, line in enumerate(emitted) if line.startswith("BACKUP ") and str(destination) in line)
    assert emitted.index(f"LINK[hardlink] {destination} -> {alpha}") > backup


def test_check_reports_a_rewritten_hard_link_target_as_drift_and_keeps_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = rule_file(tmp_path, "alpha", "old body")
    deny_file_symlinks(monkeypatch)
    state = engine._sync_links(projection(tmp_path, {"alpha": alpha}), a_pass(Mode.SYNC, "nt", []))
    rewrite(alpha, "new body")
    destination = tmp_path / "home" / ".claude" / "rules" / "alpha.md"
    run_pass = a_pass(Mode.CHECK, "nt", [])

    engine._sync_links(projection(tmp_path, {"alpha": alpha}, state), run_pass)

    assert run_pass.result.drift >= 1
    assert destination.read_text(encoding="utf-8") == "old body"
    assert backed_up_bodies(tmp_path) == []


def stale_file_link(tmp_path: Path, platform: str, change: str) -> tuple[Path, Path]:
    """A recorded rule link at alpha.md that no longer points at its RULE.md."""
    target = rule_file(tmp_path, "alpha", "old body")
    destination = tmp_path / "home" / ".claude" / "rules" / "alpha.md"
    destination.parent.mkdir(parents=True)
    if platform == "nt":
        os.link(target, destination)
        if change == "rewritten":
            rewrite(target, "new body")
        else:
            target.unlink()
    else:
        destination.write_text("old body", encoding="utf-8")
    return target, destination


@pytest.mark.parametrize(("platform", "change"), [("nt", "rewritten"), ("nt", "deleted"), ("posix", "replaced")])
def test_sync_backs_up_a_stale_file_link_that_no_longer_points_at_its_target(
    tmp_path: Path, platform: str, change: str
) -> None:
    target, destination = stale_file_link(tmp_path, platform, change)
    emitted: list[str] = []
    run_pass = a_pass(Mode.SYNC, platform, emitted)

    engine._remove_stale_links(projection(tmp_path, {}, {"alpha": str(target)}), run_pass)

    assert not os.path.lexists(destination)
    assert run_pass.result.drift == 1
    assert backed_up_bodies(tmp_path) == ["old body"]
    assert any(line.startswith("BACKUP ") and str(destination) in line for line in emitted)


@pytest.mark.parametrize("mode", [Mode.CHECK, Mode.DRY_RUN])
def test_read_only_pass_reports_a_changed_stale_file_link_and_keeps_it(tmp_path: Path, mode: Mode) -> None:
    target, destination = stale_file_link(tmp_path, "nt", "rewritten")
    emitted: list[str] = []

    engine._remove_stale_links(projection(tmp_path, {}, {"alpha": str(target)}), a_pass(mode, "nt", emitted))

    assert emitted == [f"MISMATCH CHANGED {destination}"]
    assert destination.read_text(encoding="utf-8") == "old body"
    assert backed_up_bodies(tmp_path) == []


def test_sync_still_refuses_to_clean_a_changed_stale_directory_link(tmp_path: Path) -> None:
    skill = tmp_path / "source" / "skills" / "alpha"
    skill.mkdir(parents=True)
    project = projection(tmp_path, {}, {"alpha": str(skill)}, entry_suffix="", file_links=False)
    stale = project.destination_root / "alpha"
    stale.mkdir()

    with pytest.raises(BraidError, match="refusing to clean changed managed path"):
        engine._remove_stale_links(project, a_pass(Mode.SYNC, "nt", []))

    assert stale.is_dir()
    assert backed_up_bodies(tmp_path) == []


@pytest.mark.parametrize("platform", ["nt", "posix"])
def test_sync_removes_a_stale_file_link_that_still_points_at_its_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    alpha = rule_file(tmp_path, "alpha", "alpha body")
    if platform == "nt":
        deny_file_symlinks(monkeypatch)
    state = engine._sync_links(projection(tmp_path, {"alpha": alpha}), a_pass(Mode.SYNC, platform, []))
    destination = tmp_path / "home" / ".claude" / "rules" / "alpha.md"

    engine._remove_stale_links(projection(tmp_path, {}, state), a_pass(Mode.SYNC, platform, []))

    assert not os.path.lexists(destination)
    assert alpha.read_text(encoding="utf-8") == "alpha body"
    assert backed_up_bodies(tmp_path) == []


@pytest.mark.parametrize("platform", ["nt", "posix"])
def test_points_to_accepts_a_windows_hard_link_only_on_windows(tmp_path: Path, platform: str) -> None:
    target = rule_file(tmp_path, "alpha", "alpha body")
    linked = tmp_path / "linked.md"
    os.link(target, linked)

    assert engine._points_to(linked, target, platform) is (platform == "nt")


def test_points_to_rejects_a_windows_copy_with_identical_content(tmp_path: Path) -> None:
    target = rule_file(tmp_path, "alpha", "alpha body")
    copy = tmp_path / "copy.md"
    copy.write_text("alpha body", encoding="utf-8")

    assert engine._points_to(copy, target, "nt") is False


def test_points_to_rejects_a_windows_hard_link_whose_target_is_gone(tmp_path: Path) -> None:
    target = rule_file(tmp_path, "alpha", "alpha body")
    linked = tmp_path / "linked.md"
    os.link(target, linked)
    target.unlink()

    assert engine._points_to(linked, target, "nt") is False


def test_remove_owned_link_unlinks_a_windows_hard_link_and_keeps_the_target(tmp_path: Path) -> None:
    target = rule_file(tmp_path, "alpha", "alpha body")
    linked = tmp_path / "linked.md"
    os.link(target, linked)

    engine._remove_owned_link(linked, target, "nt")

    assert not os.path.lexists(linked)
    assert target.read_text(encoding="utf-8") == "alpha body"


def test_remove_owned_link_refuses_a_windows_file_that_is_not_the_target(tmp_path: Path) -> None:
    target = rule_file(tmp_path, "alpha", "alpha body")
    copy = tmp_path / "copy.md"
    copy.write_text("alpha body", encoding="utf-8")

    with pytest.raises(BraidError):
        engine._remove_owned_link(copy, target, "nt")

    assert copy.read_text(encoding="utf-8") == "alpha body"


BACKUP_SUFFIX = re.compile(r"(\d{8}-\d{6}-\d{6})-(\d+)")


@pytest.mark.parametrize("pid", [4242, 77])
def test_backup_suffix_is_a_microsecond_timestamp_then_the_process_id(
    monkeypatch: pytest.MonkeyPatch, pid: int
) -> None:
    monkeypatch.setattr(os, "getpid", lambda: pid)

    suffix = engine._backup_suffix()

    match = BACKUP_SUFFIX.fullmatch(suffix)
    assert match is not None
    assert match.group(2) == str(pid)
    stamped = datetime.strptime(match.group(1), "%Y%m%d-%H%M%S-%f")
    assert abs(datetime.now() - stamped) < timedelta(seconds=5)


def test_two_backup_suffixes_in_one_process_share_the_real_pid() -> None:
    first = engine._backup_suffix()
    second = engine._backup_suffix()

    assert first.endswith(f"-{os.getpid()}")
    assert second.endswith(f"-{os.getpid()}")
    assert second >= first
