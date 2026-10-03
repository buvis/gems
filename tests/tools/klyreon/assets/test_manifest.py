"""Phase 0 -- the installed-artifact manifest store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from klyreon.assets.manifest import (
    SCHEMA_VERSION,
    Manifest,
    ManifestEntry,
    ManifestError,
    entries_for,
    load_manifest,
    manifest_path,
    save_manifest,
)

pytestmark = pytest.mark.klyreon


@pytest.fixture
def xdg_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    return state


def _entry(path: str, operator: str = "claude", kind: str = "asset") -> ManifestEntry:
    return ManifestEntry(
        kind=kind,
        operator=operator,
        path=path,
        sha256="deadbeef",
        klyreon_version="0.1.0",
        installed_at="2026-10-03T00:00:00+00:00",
    )


class TestManifestRoundTrip:
    def test_missing_manifest_loads_empty(self, xdg_state: Path) -> None:
        m = load_manifest()
        assert m.schema_version == SCHEMA_VERSION
        assert m.entries == []
        assert not manifest_path().exists(), "loading must not create the file"

    def test_save_then_load_round_trips(self, xdg_state: Path) -> None:
        m = Manifest(entries=[_entry("/home/x/.claude/skills/klyreon/SKILL.md")])
        save_manifest(m)
        loaded = load_manifest()
        assert loaded.schema_version == SCHEMA_VERSION
        assert len(loaded.entries) == 1
        assert loaded.entries[0] == m.entries[0]

    def test_manifest_written_atomically_as_json(self, xdg_state: Path) -> None:
        save_manifest(Manifest(entries=[_entry("/a")]))
        raw = json.loads(manifest_path().read_text(encoding="utf-8"))
        assert raw["schema_version"] == SCHEMA_VERSION
        assert raw["entries"][0]["path"] == "/a"

    def test_upsert_replaces_same_path(self, xdg_state: Path) -> None:
        m = Manifest(entries=[_entry("/a")])
        m.upsert(ManifestEntry("asset", "claude", "/a", "newhash", "0.2.0", "t"))
        assert len(m.entries) == 1
        assert m.entries[0].sha256 == "newhash"

    def test_remove_path_drops_entry(self, xdg_state: Path) -> None:
        m = Manifest(entries=[_entry("/a"), _entry("/b")])
        m.remove_path("/a")
        assert [e.path for e in m.entries] == ["/b"]


class TestManifestLoudFailures:
    def test_unknown_schema_version_fails_loudly(self, xdg_state: Path) -> None:
        manifest_path().parent.mkdir(parents=True, exist_ok=True)
        manifest_path().write_text(json.dumps({"schema_version": 99, "entries": []}), encoding="utf-8")
        with pytest.raises(ManifestError, match="unknown schema_version 99"):
            load_manifest()

    def test_non_integer_schema_version_fails(self, xdg_state: Path) -> None:
        manifest_path().parent.mkdir(parents=True, exist_ok=True)
        manifest_path().write_text(json.dumps({"schema_version": "1", "entries": []}), encoding="utf-8")
        with pytest.raises(ManifestError, match="non-integer schema_version"):
            load_manifest()

    def test_non_object_top_level_fails(self, xdg_state: Path) -> None:
        manifest_path().parent.mkdir(parents=True, exist_ok=True)
        manifest_path().write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ManifestError, match="must be a JSON object"):
            load_manifest()

    def test_malformed_json_fails(self, xdg_state: Path) -> None:
        manifest_path().parent.mkdir(parents=True, exist_ok=True)
        manifest_path().write_text("{not json", encoding="utf-8")
        with pytest.raises(ManifestError, match="unreadable"):
            load_manifest()


class TestEntriesFor:
    def test_filters_by_kind_and_operator(self, xdg_state: Path) -> None:
        save_manifest(
            Manifest(
                entries=[
                    _entry("/a", operator="claude", kind="asset"),
                    _entry("/b", operator="kiro", kind="asset"),
                    _entry("/c", operator="claude", kind="schedule"),
                ],
            ),
        )
        assets = entries_for("asset")
        assert {e.path for e in assets} == {"/a", "/b"}
        claude_assets = entries_for("asset", "claude")
        assert {e.path for e in claude_assets} == {"/a"}
        schedules = entries_for("schedule")
        assert {e.path for e in schedules} == {"/c"}
