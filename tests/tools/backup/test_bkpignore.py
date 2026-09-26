from __future__ import annotations

from backup.shared.bkpignore import BkpignoreRules, ExcludeState, parse_bkpignore


class TestParseBkpignore:
    def test_bare_lines_are_adds(self) -> None:
        rules = parse_bkpignore("logs\ntmp\n")
        assert rules.adds == ("logs", "tmp")
        assert rules.unignores == ()

    def test_bang_lines_are_unignores(self) -> None:
        rules = parse_bkpignore("!target\n!dist\n")
        assert rules.unignores == ("target", "dist")
        assert rules.adds == ()

    def test_comments_and_blanks_ignored(self) -> None:
        rules = parse_bkpignore("# a comment\n\n  \nlogs\n")
        assert rules.adds == ("logs",)

    def test_whitespace_stripped(self) -> None:
        rules = parse_bkpignore("  logs  \n  ! target \n")
        assert rules.adds == ("logs",)
        assert rules.unignores == ("target",)

    def test_escaped_bang_is_literal_add(self) -> None:
        rules = parse_bkpignore("\\!weird\n")
        assert rules.adds == ("!weird",)

    def test_duplicate_lines_deduped(self) -> None:
        rules = parse_bkpignore("logs\nlogs\n!target\n!target\n")
        assert rules.adds == ("logs",)
        assert rules.unignores == ("target",)


class TestExcludeState:
    def test_global_exclude_matches_basename(self) -> None:
        state = ExcludeState(excludes=frozenset({"target"}))
        assert state.is_excluded("target") is True
        assert state.is_excluded("src") is False

    def test_glob_exclude(self) -> None:
        state = ExcludeState(excludes=frozenset({"*.pyc"}))
        assert state.is_excluded("mod.pyc") is True
        assert state.is_excluded("mod.py") is False

    def test_unignore_cancels_exclude(self) -> None:
        state = ExcludeState(excludes=frozenset({"target"})).layer(
            BkpignoreRules(unignores=("target",)),
        )
        assert state.is_excluded("target") is False

    def test_add_extends_excludes(self) -> None:
        state = ExcludeState().layer(BkpignoreRules(adds=("logs",)))
        assert state.is_excluded("logs") is True

    def test_slash_pattern_matches_relpath_not_basename(self) -> None:
        state = ExcludeState(excludes=frozenset({".yarn/cache"}))
        # basename "cache" alone must NOT match the slash pattern
        assert state.is_excluded("cache", "somewhere/cache") is False
        # the source-relative path must match
        assert state.is_excluded("cache", ".yarn/cache") is True

    def test_layer_is_immutable_on_parent(self) -> None:
        parent = ExcludeState(excludes=frozenset({"target"}))
        child = parent.layer(BkpignoreRules(unignores=("target",)))
        # parent state is untouched: only the child subtree un-ignores target
        assert parent.is_excluded("target") is True
        assert child.is_excluded("target") is False

    def test_applied_records_layered_rules(self) -> None:
        state = ExcludeState().layer(BkpignoreRules(adds=("logs",), unignores=("target",)))
        assert "+logs" in state.applied
        assert "!target" in state.applied
