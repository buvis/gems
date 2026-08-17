"""Tests for CommandResult and JSON-safe conversion."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from buvis.pybase.result import CommandResult, _json_safe, notify_result


def _notify_stub() -> tuple[list[tuple[str, str]], Callable[..., None]]:
    """Build a list-collecting stand-in for Textual's `notify` callable."""
    calls: list[tuple[str, str]] = []

    def notify(message: str, *, severity: str = "information") -> None:
        calls.append((message, severity))

    return calls, notify


class TestCommandResult:
    def test_to_dict_produces_json_safe_dict(self) -> None:
        metadata = {
            "path": Path("notes"),
            "nested": {"items": [Path("one"), "two"]},
        }
        result = CommandResult(success=True, output="ok", metadata=metadata)

        assert result.to_dict() == {
            "success": True,
            "output": "ok",
            "error": None,
            "info": [],
            "warnings": [],
            "metadata": {"path": "notes", "nested": {"items": ["one", "two"]}},
        }

    def test_warnings_serialize_correctly(self) -> None:
        result = CommandResult(success=True, warnings=["first", "second"])

        assert result.to_dict()["warnings"] == ["first", "second"]

    def test_success_with_output(self) -> None:
        result = CommandResult(success=True, output="done")

        assert result.success is True
        assert result.output == "done"
        assert result.error is None

    def test_failure_with_error(self) -> None:
        result = CommandResult(success=False, error="failed")

        assert result.success is False
        assert result.output is None
        assert result.error == "failed"

    def test_empty_success(self) -> None:
        result = CommandResult(success=True)

        assert result.success is True
        assert result.output is None
        assert result.error is None

    def test_partial_success_with_warnings(self) -> None:
        result = CommandResult(success=True, output="ok", warnings=["warned"])

        assert result.success is True
        assert result.output == "ok"
        assert result.warnings == ["warned"]


class TestJsonSafe:
    def test_converts_nested_paths_in_dicts_and_lists(self) -> None:
        data = {
            "path": Path("root"),
            "items": [Path("a"), {"child": Path("b")}],
            "tuple": (Path("c"),),
        }

        assert _json_safe(data) == {
            "path": "root",
            "items": ["a", {"child": "b"}],
            "tuple": ["c"],
        }


class TestNotifyResult:
    def test_success_with_output_notifies_information(self) -> None:
        calls, notify = _notify_stub()
        result = CommandResult(success=True, output="Created note.md")

        notify_result(result, notify)

        assert calls == [("Created note.md", "information")]

    def test_success_without_output_notifies_nothing(self) -> None:
        calls, notify = _notify_stub()
        result = CommandResult(success=True)

        notify_result(result, notify)

        assert calls == []

    def test_failure_with_error_notifies_error_severity(self) -> None:
        calls, notify = _notify_stub()
        result = CommandResult(success=False, error="Missing required answer: type")

        notify_result(result, notify)

        assert calls == [("Missing required answer: type", "error")]

    def test_failure_without_error_falls_back_to_default_message(self) -> None:
        calls, notify = _notify_stub()
        result = CommandResult(success=False)

        notify_result(result, notify)

        assert calls == [("Failed", "error")]

    def test_warnings_notify_before_success_output(self) -> None:
        calls, notify = _notify_stub()
        result = CommandResult(success=True, output="ok", warnings=["heads up"])

        notify_result(result, notify)

        assert calls == [("heads up", "warning"), ("ok", "information")]

    def test_warnings_notify_alongside_failure(self) -> None:
        calls, notify = _notify_stub()
        result = CommandResult(success=False, error="bad", warnings=["heads up"])

        notify_result(result, notify)

        assert calls == [("heads up", "warning"), ("bad", "error")]

    def test_multiple_warnings_each_notify_independently(self) -> None:
        calls, notify = _notify_stub()
        result = CommandResult(success=True, warnings=["first warning", "second warning"])

        notify_result(result, notify)

        assert calls == [
            ("first warning", "warning"),
            ("second warning", "warning"),
        ]
