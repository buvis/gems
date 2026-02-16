"""Tests for CommandResult and JSON-safe conversion."""

from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult, _json_safe


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
