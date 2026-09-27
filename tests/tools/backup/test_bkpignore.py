from __future__ import annotations

from backup.shared.bkpignore import (
    BkpignoreRules,
    ExcludeState,
    parse_bkpignore,
    resolve_state_for_path,
)


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
        state = ExcludeState(base_excludes=frozenset({"target"}))
        assert state.is_excluded("target") is True
        assert state.is_excluded("src") is False

    def test_glob_exclude(self) -> None:
        state = ExcludeState(base_excludes=frozenset({"*.pyc"}))
        assert state.is_excluded("mod.pyc") is True
        assert state.is_excluded("mod.py") is False

    def test_unignore_cancels_exclude(self) -> None:
        state = ExcludeState(base_excludes=frozenset({"target"})).layer(
            BkpignoreRules(unignores=("target",)),
        )
        assert state.is_excluded("target") is False

    def test_add_extends_excludes(self) -> None:
        state = ExcludeState().layer(BkpignoreRules(adds=("logs",)))
        assert state.is_excluded("logs") is True

    def test_slash_pattern_matches_relpath_not_basename(self) -> None:
        state = ExcludeState(base_excludes=frozenset({".yarn/cache"}))
        # basename "cache" alone must NOT match the slash pattern
        assert state.is_excluded("cache", "somewhere/cache") is False
        # the source-relative path must match
        assert state.is_excluded("cache", ".yarn/cache") is True

    def test_layer_is_immutable_on_parent(self) -> None:
        parent = ExcludeState(base_excludes=frozenset({"target"}))
        child = parent.layer(BkpignoreRules(unignores=("target",)))
        # parent state is untouched: only the child subtree un-ignores target
        assert parent.is_excluded("target") is True
        assert child.is_excluded("target") is False

    def test_applied_records_layered_rules(self) -> None:
        state = ExcludeState().layer(BkpignoreRules(adds=("logs",), unignores=("target",)))
        assert "+logs" in state.applied
        assert "!target" in state.applied


class TestExcludeStatePrecedence:
    """Finding 2: gitignore-style precedence — descendant/later layer wins."""

    def test_descendant_plain_reexcludes_ancestor_unignore(self) -> None:
        # ancestor `!target` un-ignores; a descendant plain `target` re-excludes.
        ancestor = ExcludeState(base_excludes=frozenset({"target"})).layer(
            BkpignoreRules(unignores=("target",)),
        )
        assert ancestor.is_excluded("target") is False
        descendant = ancestor.layer(BkpignoreRules(adds=("target",)))
        assert descendant.is_excluded("target") is True

    def test_ancestor_unignore_alone_still_unignores(self) -> None:
        # existing behaviour: `!target` alone keeps target/ against the global default.
        state = ExcludeState(base_excludes=frozenset({"target"})).layer(
            BkpignoreRules(unignores=("target",)),
        )
        assert state.is_excluded("target") is False

    def test_same_file_later_line_overrides_earlier(self) -> None:
        # within one .bkpignore, a later line wins over an earlier one.
        rules = parse_bkpignore("!target\ntarget\n")
        state = ExcludeState(base_excludes=frozenset({"target"})).layer(rules)
        assert state.is_excluded("target") is True
        rules_rev = parse_bkpignore("target\n!target\n")
        state_rev = ExcludeState().layer(rules_rev)
        assert state_rev.is_excluded("target") is False

    def test_pattern_repeated_after_its_opposite_last_wins(self) -> None:
        # regression: `target`, `!target`, `target` — dedup must not drop the
        # final add from `sequence`; the last line (plain add) wins.
        rules = parse_bkpignore("target\n!target\ntarget\n")
        assert rules.sequence == (("target", False), ("target", True), ("target", False))
        state = ExcludeState().layer(rules)
        assert state.is_excluded("target") is True
        # and the mirror: ending on `!target` un-ignores.
        rules_unignore_last = parse_bkpignore("!target\ntarget\n!target\n")
        state2 = ExcludeState(base_excludes=frozenset({"target"})).layer(rules_unignore_last)
        assert state2.is_excluded("target") is False


class TestResolveStateForPath:
    """Finding 7: a --for target outside source returns base_state unchanged."""

    def test_outside_source_returns_base_state_no_source_bkpignore(self, tmp_path) -> None:
        source = tmp_path / "src"
        (source / "repoA").mkdir(parents=True)
        # a source-root .bkpignore that must NOT be applied for an outside target
        (source / ".bkpignore").write_text("!target\n", encoding="utf-8")
        outside = tmp_path / "elsewhere"
        outside.mkdir()

        base_state = ExcludeState(base_excludes=frozenset({"target"}))
        state = resolve_state_for_path(source, base_state, outside)

        # identical to base: no .bkpignore layers, only the global excludes
        assert state == base_state
        assert state.applied == ()
        assert state.is_excluded("target") is True

    def test_inside_source_does_layer_root_bkpignore(self, tmp_path) -> None:
        source = tmp_path / "src"
        (source / "repoA").mkdir(parents=True)
        (source / ".bkpignore").write_text("!target\n", encoding="utf-8")
        base_state = ExcludeState(base_excludes=frozenset({"target"}))
        state = resolve_state_for_path(source, base_state, source / "repoA")
        assert "!target" in state.applied
        assert state.is_excluded("target") is False


class TestResolveStateSymlinkEscape:
    """FIX G: a source/link symlink pointing outside source must NOT let
    .bkpignore files OUTSIDE the source tree be read (lexical relative_to bug)."""

    def test_symlink_out_of_source_does_not_apply_outside_bkpignore(self, tmp_path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        # an outside dir carrying a .bkpignore that must NEVER apply
        (outside / ".bkpignore").write_text("!target\n", encoding="utf-8")
        link = source / "link"
        link.symlink_to(outside, target_is_directory=True)

        base_state = ExcludeState(base_excludes=frozenset({"target"}))
        state = resolve_state_for_path(source, base_state, link)

        # resolved containment rejects the escaped anchor -> base_state, so the
        # outside .bkpignore's `!target` is NOT applied and target stays excluded.
        assert state == base_state
        assert state.applied == ()
        assert state.is_excluded("target") is True

    def test_symlink_pointing_into_source_still_layers(self, tmp_path) -> None:
        # a symlink that resolves back INSIDE source must still layer normally.
        source = tmp_path / "src"
        (source / "real").mkdir(parents=True)
        (source / "real" / ".bkpignore").write_text("!target\n", encoding="utf-8")
        link = source / "alias"
        link.symlink_to(source / "real", target_is_directory=True)

        base_state = ExcludeState(base_excludes=frozenset({"target"}))
        state = resolve_state_for_path(source, base_state, link)
        assert "!target" in state.applied
        assert state.is_excluded("target") is False


class TestResolveStatePruning:
    """The introspection resolver must match the archive walk's pruning: it must
    not read a .bkpignore under a directory the walk would never descend into."""

    def test_excluded_dir_on_path_is_not_layered(self, tmp_path) -> None:
        # global excludes contain `target`; a .bkpignore INSIDE target would be
        # read by a naive resolver, but the archive walk prunes `target` before
        # descending, so its rules must NOT appear.
        source = tmp_path / "src"
        (source / "target").mkdir(parents=True)
        (source / "target" / ".bkpignore").write_text("!secret\n", encoding="utf-8")
        base_state = ExcludeState(base_excludes=frozenset({"target"}))
        state = resolve_state_for_path(source, base_state, source / "target")
        # pruned at the target boundary -> no target/.bkpignore rule layered
        assert state.applied == ()
        assert "!secret" not in state.applied
        # and target itself is still excluded by the global default
        assert state.is_excluded("target") is True

    def test_unexcluded_dir_on_path_is_layered(self, tmp_path) -> None:
        # a non-excluded directory on the path IS descended and its .bkpignore read.
        source = tmp_path / "src"
        (source / "repo").mkdir(parents=True)
        (source / "repo" / ".bkpignore").write_text("!target\n", encoding="utf-8")
        base_state = ExcludeState(base_excludes=frozenset({"target"}))
        state = resolve_state_for_path(source, base_state, source / "repo")
        assert "!target" in state.applied
