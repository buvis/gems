from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from sysup.step_result import RED, StepResult


class TestStepResult:
    @pytest.mark.parametrize("success,status", [(True, "ok"), (False, "failed")])
    def test_status_derives_from_success(self, success: bool, status: str) -> None:
        result = StepResult("brew", success, "message")
        assert result.status == status
        assert result.message == "message"
        assert result.command == ""
        assert result.kind == "command"

    @pytest.mark.parametrize("status", ["failed", "expiring", "expired", "unknown"])
    @pytest.mark.parametrize("success", [True, False])
    def test_explicit_status_is_kept(self, status, success: bool) -> None:
        result = StepResult("certificate", success, status=status, kind="item")
        assert result.status == status
        assert result.kind == "item"

    def test_frozen_result_can_be_replaced_without_mutation(self) -> None:
        result = StepResult("pip (3.12)", False, "boom")
        with pytest.raises(FrozenInstanceError):
            result.command = "pip"
        stamped = replace(result, command="python-packages")
        assert stamped.command == "python-packages"
        assert stamped.label == result.label
        assert stamped.status == "failed"
        assert result.command == ""

    def test_red_statuses(self) -> None:
        assert RED == frozenset({"failed", "expired", "unknown"})

    def test_warned_status_is_kept_with_success_true(self) -> None:
        result = StepResult("brew", True, "1 error line(s), see log", status="warned")
        assert result.status == "warned"
        assert result.success is True

    def test_warned_is_not_red(self) -> None:
        assert "warned" not in RED
