from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import pytest

from sysup.attention import exit_code, fold_results, mark_notified, read_state, state_path, to_notify, write_state
from sysup.step_result import StepResult

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 10, 14, 12, 30, 45, tzinfo=timezone.utc)
_STAMP = "2026-10-14T12:30:45+00:00"


def _entry(status: str = "failed", *, notified: bool = False) -> dict[str, Any]:
    return {
        "kind": "command",
        "status": status,
        "details": ["boom"],
        "first_seen": _STAMP,
        "last_checked": _STAMP,
        "notified": notified,
    }


class TestFoldResults:
    def test_failed_command_creates_one_entry_with_every_failure(self) -> None:
        results = [
            StepResult("numpy (3.12)", False, "numpy failed", command="python-packages"),
            StepResult("requests (3.12)", False, "requests failed", command="python-packages"),
        ]
        entries = fold_results({}, {"python-packages"}, results, _NOW)
        assert entries == {
            "python-packages": {
                **_entry(),
                "details": ["numpy failed", "requests failed"],
            }
        }

    def test_success_after_failure_in_same_run_keeps_entry(self) -> None:
        results = [
            StepResult("numpy (3.12)", False, "numpy failed", command="python-packages"),
            StepResult("requests (3.12)", True, command="python-packages"),
        ]
        entries = fold_results({}, {"python-packages"}, results, _NOW)
        assert entries["python-packages"]["details"] == ["numpy failed"]
        assert entries["python-packages"]["status"] == "failed"

    def test_complete_success_clears_entry(self) -> None:
        previous = {"brew": _entry()}
        assert fold_results(previous, {"brew"}, [StepResult("brew", True)], _NOW) == {}
        assert fold_results(previous, {"brew"}, [], _NOW) == {}
        assert previous == {"brew": _entry()}

    def test_unchecked_names_keep_entries(self) -> None:
        entries = {"helm": _entry()}
        assert fold_results(entries, {"brew"}, [StepResult("brew", True)], _NOW) == entries

    def test_worst_status_kind_and_fallback_detail(self) -> None:
        results = [
            StepResult("certificate", True, status="expiring", command="expiry", kind="item"),
            StepResult("license", False, "unknown license", status="unknown", command="expiry", kind="item"),
            StepResult("token", False, "expired token", status="expired", command="expiry", kind="item"),
            StepResult("probe", False, "failed probe", command="expiry"),
        ]
        entries = fold_results({}, {"expiry"}, results, _NOW)
        assert entries["expiry"]["status"] == "failed"
        assert entries["expiry"]["kind"] == "item"
        assert entries["expiry"]["details"] == [
            "certificate expiring",
            "unknown license",
            "expired token",
            "failed probe",
        ]

    @pytest.mark.parametrize(
        "statuses,worst",
        [
            (["expiring", "unknown"], "unknown"),
            (["unknown", "expired"], "expired"),
            (["expired", "failed"], "failed"),
        ],
    )
    def test_ranking(self, statuses, worst: str) -> None:
        results = [StepResult("check", True, status=status) for status in statuses]
        assert fold_results({}, set(), results, _NOW)["check"]["status"] == worst

    def test_stamp_is_utc_seconds_and_previous_metadata_survives(self) -> None:
        later = datetime(2026, 10, 15, 19, 30, 12, 987654, tzinfo=timezone(timedelta(hours=2)))
        previous = {"brew": _entry(notified=True)}
        entries = fold_results(previous, {"brew"}, [StepResult("brew", False, "new failure")], later)
        assert entries["brew"]["first_seen"] == _STAMP
        assert entries["brew"]["last_checked"] == "2026-10-15T17:30:12+00:00"
        assert entries["brew"]["notified"] is True
        assert entries["brew"]["details"] == ["new failure"]
        assert previous == {"brew": _entry(notified=True)}

    def test_inputs_are_not_mutated_and_result_names_join_checked(self) -> None:
        entries = {"helm": _entry()}
        checked = {"brew"}
        results = [StepResult("probe", False)]
        before = copy.deepcopy((entries, checked, results))
        folded = fold_results(entries, checked, results, _NOW)
        assert (entries, checked, results) == before
        assert set(folded) == {"helm", "probe"}
        assert folded["probe"]["details"] == ["probe failed"]


class TestAttentionDecisions:
    def test_red_entries_notify_every_run_amber_once(self) -> None:
        entries = {
            "z-amber": _entry("expiring"),
            "failed": _entry(),
            "expired": _entry("expired"),
            "unknown": _entry("unknown"),
        }
        names = ["expired", "failed", "unknown", "z-amber"]
        assert to_notify(entries) == names
        pushed = mark_notified(entries, names)
        assert to_notify(pushed) == ["expired", "failed", "unknown"]
        assert to_notify(mark_notified(pushed, to_notify(pushed))) == ["expired", "failed", "unknown"]
        assert entries["z-amber"]["notified"] is False

    def test_red_to_amber_stays_quiet_amber_to_red_pushes(self) -> None:
        previous = {"certificate": {**_entry("expired", notified=True), "kind": "item"}}
        amber = fold_results(
            previous, {"certificate"}, [StepResult("certificate", True, status="expiring", kind="item")], _NOW
        )
        assert to_notify(amber) == []
        red = fold_results(
            amber, {"certificate"}, [StepResult("certificate", False, status="expired", kind="item")], _NOW
        )
        assert to_notify(red) == ["certificate"]

    def test_mark_notified_changes_only_selected_without_mutation(self) -> None:
        entries = {"brew": _entry(), "certificate": _entry("expiring")}
        before = copy.deepcopy(entries)
        marked = mark_notified(entries, ["brew"])
        assert marked["brew"]["notified"] is True
        assert marked["certificate"]["notified"] is False
        assert entries == before

    def test_exit_code_counts_only_this_run(self) -> None:
        retained = {"helm": _entry()}
        results = [StepResult("brew", True)]
        assert fold_results(retained, {"brew"}, results, _NOW) == retained
        assert exit_code(results) == 0
        assert exit_code([]) == 0
        assert exit_code([StepResult("certificate", True, status="expiring", kind="item")]) == 0

    @pytest.mark.parametrize("status", ["failed", "expired", "unknown"])
    def test_exit_code_counts_every_red_status_not_success_flag(self, status) -> None:
        assert exit_code([StepResult("check", True, status=status)]) == 1


class TestAttentionState:
    def test_state_roundtrip_under_xdg_state_home(self, tmp_path: Path) -> None:
        path = state_path()
        assert path == tmp_path / "state" / "sysup" / "attention.json"
        assert read_state() == {}
        entries = {"brew": _entry(), "certificate": {**_entry("expiring"), "kind": "item"}}
        write_state(entries)
        assert read_state() == entries
        assert path.read_text() == json.dumps({"version": 1, "entries": entries}, indent=2, sort_keys=True) + "\n"
        assert list(path.parent.iterdir()) == [path]
        path.write_text("{malformed")
        assert read_state() == {}

    def test_xdg_fallback_path(self, monkeypatch, tmp_path: Path) -> None:
        from pathlib import Path

        monkeypatch.delenv("XDG_STATE_HOME")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert state_path() == tmp_path / ".local" / "state" / "sysup" / "attention.json"

    @pytest.mark.parametrize(
        "document",
        [
            None,
            [],
            {},
            {"entries": {}},
            {"version": 1},
            {"version": 2, "entries": {}},
            {"version": True, "entries": {}},
            {"version": 1.0, "entries": {}},
            {"version": 1, "entries": []},
            {"version": 1, "entries": {}, "extra": True},
            {"version": 1, "entries": {"brew": None}},
            {"version": 1, "entries": {"brew": {}}},
        ],
    )
    def test_malformed_envelope_or_entry_is_empty(self, document) -> None:
        path = state_path()
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(document))
        assert read_state() == {}

    @pytest.mark.parametrize(
        "field,value",
        [
            ("kind", "other"),
            ("kind", []),
            ("status", "ok"),
            ("status", []),
            ("details", []),
            ("details", "boom"),
            ("details", [1]),
            ("first_seen", None),
            ("last_checked", 1),
            ("notified", 1),
            ("notified", "false"),
            ("extra", True),
        ],
    )
    def test_malformed_entry_field_invalidates_entire_state(self, field: str, value) -> None:
        malformed = {**_entry(), field: value}
        write_state({"valid": _entry(), "invalid": malformed})
        assert read_state() == {}

    def test_missing_entry_field_is_empty(self) -> None:
        entry = _entry()
        del entry["first_seen"]
        write_state({"brew": entry})
        assert read_state() == {}

    def test_invalid_unicode_is_empty(self) -> None:
        path = state_path()
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\xff")
        assert read_state() == {}

    def test_unreadable_state_is_empty(self, mocker) -> None:
        mocker.patch("sysup.attention.Path.read_text", side_effect=PermissionError("denied"))
        assert read_state() == {}

    def test_atomic_write_failure_preserves_existing_state_and_cleans_sibling(self, mocker) -> None:
        write_state({"brew": _entry()})
        path = state_path()
        before = path.read_bytes()
        mocker.patch("buvis.pybase.filesystem.atomic_write.os.replace", side_effect=OSError("full"))
        with pytest.raises(OSError, match="full"):
            write_state({})
        assert path.read_bytes() == before
        assert list(path.parent.iterdir()) == [path]
