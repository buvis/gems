"""Tests for RULE_CONFLICT triage reason helpers in shared.triage."""

from __future__ import annotations

import pytest


class TestFormatRuleConflictReason:
    def test_two_ids_alphabetical(self) -> None:
        from bim.commands.doc.shared.triage import format_rule_conflict_reason

        result = format_rule_conflict_reason(["b-rule", "a-rule"])
        assert result == "rule_conflict: a-rule vs b-rule"

    def test_three_ids_alphabetical(self) -> None:
        from bim.commands.doc.shared.triage import format_rule_conflict_reason

        result = format_rule_conflict_reason(["c-rule", "a-rule", "b-rule"])
        assert result == "rule_conflict: a-rule vs b-rule vs c-rule"

    def test_already_sorted_two(self) -> None:
        from bim.commands.doc.shared.triage import format_rule_conflict_reason

        assert format_rule_conflict_reason(["alpha", "beta"]) == "rule_conflict: alpha vs beta"

    def test_empty_list_raises(self) -> None:
        from bim.commands.doc.shared.triage import format_rule_conflict_reason

        with pytest.raises(ValueError):
            format_rule_conflict_reason([])

    def test_single_id_raises(self) -> None:
        from bim.commands.doc.shared.triage import format_rule_conflict_reason

        with pytest.raises(ValueError):
            format_rule_conflict_reason(["lone-rule"])


class TestReasonPrefixConstant:
    def test_prefix_exposed(self) -> None:
        from bim.commands.doc.shared.triage import RULE_CONFLICT_REASON_PREFIX

        assert RULE_CONFLICT_REASON_PREFIX == "rule_conflict"

    def test_format_uses_prefix(self) -> None:
        from bim.commands.doc.shared.triage import (
            RULE_CONFLICT_REASON_PREFIX,
            format_rule_conflict_reason,
        )

        result = format_rule_conflict_reason(["a", "b"])
        assert result.startswith(f"{RULE_CONFLICT_REASON_PREFIX}: ")
