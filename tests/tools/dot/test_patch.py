from __future__ import annotations

import re

from dot.tui.patch import Hunk, build_hunk_patch, build_line_patch, parse_diff, reverse_patch


SINGLE_HUNK_DIFF = """\
--- a/hello.py
+++ b/hello.py
@@ -1,3 +1,4 @@
 import os
+import sys

 print("hello")
"""

MULTI_HUNK_DIFF = """\
--- a/app.py
+++ b/app.py
@@ -2,6 +2,7 @@
 import os
 import sys
+import json

 def main():
     pass
@@ -15,4 +16,5 @@
 def cleanup():
     os.remove("tmp")
+    os.remove("cache")
     print("done")
"""

ADDITIONS_ONLY_DIFF = """\
--- a/new.py
+++ b/new.py
@@ -0,0 +1,3 @@
+line one
+line two
+line three
"""

DELETIONS_ONLY_DIFF = """\
--- a/old.py
+++ b/old.py
@@ -1,3 +0,0 @@
-removed one
-removed two
-removed three
"""

SINGLE_LINE_COUNT_DIFF = """\
--- a/cfg.txt
+++ b/cfg.txt
@@ -5 +5,2 @@
-old
+new
+extra
"""

BINARY_DIFF = "Binary files a/image.png and b/image.png differ\n"


class TestParseDiffEmpty:
    def test_empty_string_returns_empty_list(self) -> None:
        assert parse_diff("") == []

    def test_binary_diff_returns_empty_list(self) -> None:
        assert parse_diff(BINARY_DIFF) == []


class TestParseDiffSingleHunk:
    def test_returns_one_hunk(self) -> None:
        hunks = parse_diff(SINGLE_HUNK_DIFF)
        assert len(hunks) == 1

    def test_header_matches(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        assert hunk.header == "@@ -1,3 +1,4 @@"

    def test_start_old(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        assert hunk.start_old == 1

    def test_count_old(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        assert hunk.count_old == 3

    def test_start_new(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        assert hunk.start_new == 1

    def test_count_new(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        assert hunk.count_new == 4

    def test_lines_contain_content_not_header(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        assert "@@" not in "".join(hunk.lines)

    def test_lines_include_context_and_additions(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        assert " import os" in hunk.lines
        assert "+import sys" in hunk.lines


class TestParseDiffMultiHunk:
    def test_returns_two_hunks(self) -> None:
        hunks = parse_diff(MULTI_HUNK_DIFF)
        assert len(hunks) == 2

    def test_hunks_in_order(self) -> None:
        hunks = parse_diff(MULTI_HUNK_DIFF)
        assert hunks[0].start_old < hunks[1].start_old

    def test_first_hunk_header(self) -> None:
        hunks = parse_diff(MULTI_HUNK_DIFF)
        assert hunks[0].header == "@@ -2,6 +2,7 @@"

    def test_second_hunk_header(self) -> None:
        hunks = parse_diff(MULTI_HUNK_DIFF)
        assert hunks[1].header == "@@ -15,4 +16,5 @@"

    def test_first_hunk_coordinates(self) -> None:
        hunk = parse_diff(MULTI_HUNK_DIFF)[0]
        assert hunk.start_old == 2
        assert hunk.count_old == 6
        assert hunk.start_new == 2
        assert hunk.count_new == 7

    def test_second_hunk_coordinates(self) -> None:
        hunk = parse_diff(MULTI_HUNK_DIFF)[1]
        assert hunk.start_old == 15
        assert hunk.count_old == 4
        assert hunk.start_new == 16
        assert hunk.count_new == 5

    def test_each_hunk_has_own_lines(self) -> None:
        hunks = parse_diff(MULTI_HUNK_DIFF)
        assert "+import json" in hunks[0].lines
        assert "+import json" not in hunks[1].lines
        assert '+    os.remove("cache")' in hunks[1].lines
        assert '+    os.remove("cache")' not in hunks[0].lines


class TestParseDiffAdditionsOnly:
    def test_no_removal_lines(self) -> None:
        hunk = parse_diff(ADDITIONS_ONLY_DIFF)[0]
        assert not any(line.startswith("-") for line in hunk.lines)

    def test_all_lines_are_additions(self) -> None:
        hunk = parse_diff(ADDITIONS_ONLY_DIFF)[0]
        assert all(line.startswith("+") for line in hunk.lines)

    def test_count_old_is_zero(self) -> None:
        hunk = parse_diff(ADDITIONS_ONLY_DIFF)[0]
        assert hunk.count_old == 0


class TestParseDiffDeletionsOnly:
    def test_no_addition_lines(self) -> None:
        hunk = parse_diff(DELETIONS_ONLY_DIFF)[0]
        assert not any(line.startswith("+") for line in hunk.lines)

    def test_all_lines_are_deletions(self) -> None:
        hunk = parse_diff(DELETIONS_ONLY_DIFF)[0]
        assert all(line.startswith("-") for line in hunk.lines)

    def test_count_new_is_zero(self) -> None:
        hunk = parse_diff(DELETIONS_ONLY_DIFF)[0]
        assert hunk.count_new == 0


class TestParseDiffSingleLineCount:
    def test_missing_comma_means_count_one(self) -> None:
        hunk = parse_diff(SINGLE_LINE_COUNT_DIFF)[0]
        assert hunk.start_old == 5
        assert hunk.count_old == 1
        assert hunk.start_new == 5
        assert hunk.count_new == 2


class TestHunkDataclass:
    def test_hunk_is_frozen(self) -> None:
        hunk = Hunk(
            header="@@ -1,2 +1,2 @@",
            lines=[" a", "-b", "+c"],
            start_old=1,
            count_old=2,
            start_new=1,
            count_new=2,
        )
        try:
            hunk.header = "modified"  # type: ignore[misc]
            raised = False
        except AttributeError:
            raised = True
        assert raised


class TestBuildHunkPatch:
    def test_diff_git_header_contains_path(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        assert patch.startswith("diff --git a/hello.py b/hello.py\n")

    def test_minus_header_contains_path(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        assert "\n--- a/hello.py\n" in patch

    def test_plus_header_contains_path(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        assert "\n+++ b/hello.py\n" in patch

    def test_contains_hunk_header(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        assert "\n@@ -1,3 +1,4 @@\n" in patch

    def test_contains_all_hunk_lines(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        for line in hunk.lines:
            assert line in patch

    def test_ends_with_trailing_newline(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        assert patch.endswith("\n")

    def test_addition_only_hunk(self) -> None:
        hunk = parse_diff(ADDITIONS_ONLY_DIFF)[0]
        patch = build_hunk_patch("new.py", hunk)
        assert "diff --git a/new.py b/new.py\n" in patch
        assert "--- a/new.py\n" in patch
        assert "+++ b/new.py\n" in patch
        assert "@@ -0,0 +1,3 @@\n" in patch
        assert "+line one\n" in patch
        assert "+line two\n" in patch
        assert "+line three\n" in patch
        assert patch.endswith("\n")

    def test_deletion_only_hunk(self) -> None:
        hunk = parse_diff(DELETIONS_ONLY_DIFF)[0]
        patch = build_hunk_patch("old.py", hunk)
        assert "diff --git a/old.py b/old.py\n" in patch
        assert "--- a/old.py\n" in patch
        assert "+++ b/old.py\n" in patch
        assert "@@ -1,3 +0,0 @@\n" in patch
        assert "-removed one\n" in patch
        assert "-removed two\n" in patch
        assert "-removed three\n" in patch
        assert patch.endswith("\n")

    def test_mixed_hunk(self) -> None:
        hunk = Hunk(
            header="@@ -1,3 +1,3 @@",
            lines=[" context", "-old line", "+new line", " more context"],
            start_old=1,
            count_old=3,
            start_new=1,
            count_new=3,
        )
        patch = build_hunk_patch("mixed.py", hunk)
        assert "diff --git a/mixed.py b/mixed.py\n" in patch
        assert "--- a/mixed.py\n" in patch
        assert "+++ b/mixed.py\n" in patch
        assert "@@ -1,3 +1,3 @@\n" in patch
        assert " context\n" in patch
        assert "-old line\n" in patch
        assert "+new line\n" in patch
        assert " more context\n" in patch
        assert patch.endswith("\n")

    def test_path_with_subdirectory(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("src/lib/hello.py", hunk)
        assert "diff --git a/src/lib/hello.py b/src/lib/hello.py\n" in patch
        assert "--- a/src/lib/hello.py\n" in patch
        assert "+++ b/src/lib/hello.py\n" in patch


def _make_hunk() -> Hunk:
    """Shared hunk: context1, -old1, -old2, +new1, +new2, context2."""
    return Hunk(
        header="@@ -1,4 +1,4 @@",
        lines=[" context1", "-old1", "-old2", "+new1", "+new2", " context2"],
        start_old=1,
        count_old=4,
        start_new=1,
        count_new=4,
    )


def _parse_hunk_header(patch: str) -> tuple[int, int, int, int]:
    """Extract (start_old, count_old, start_new, count_new) from patch."""
    m = re.search(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@", patch)
    assert m is not None, f"No hunk header found in patch:\n{patch}"
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))


class TestBuildLinePatch:
    def test_select_all_changed_lines(self) -> None:
        hunk = _make_hunk()
        # indices 1,2 = deletions; 3,4 = additions
        patch = build_line_patch("f.py", hunk, {1, 2, 3, 4})
        _, old_count, _, new_count = _parse_hunk_header(patch)
        assert old_count == hunk.count_old
        assert new_count == hunk.count_new
        for line in hunk.lines:
            assert line in patch

    def test_select_only_additions(self) -> None:
        hunk = _make_hunk()
        # select +new1 (3) and +new2 (4); -old1, -old2 become context
        patch = build_line_patch("f.py", hunk, {3, 4})
        _, old_count, _, new_count = _parse_hunk_header(patch)
        # output lines: context1, old1(ctx), old2(ctx), +new1, +new2, context2
        assert old_count == 4  # 2 original ctx + 2 converted ctx
        assert new_count == 6  # 4 ctx + 2 additions
        assert " old1" in patch
        assert " old2" in patch
        assert "+new1" in patch
        assert "+new2" in patch

    def test_select_only_deletions(self) -> None:
        hunk = _make_hunk()
        # select -old1 (1) and -old2 (2); +new1, +new2 excluded
        patch = build_line_patch("f.py", hunk, {1, 2})
        _, old_count, _, new_count = _parse_hunk_header(patch)
        # output lines: context1, -old1, -old2, context2
        assert old_count == 4  # 2 ctx + 2 deletions
        assert new_count == 2  # 2 ctx only
        assert "-old1" in patch
        assert "-old2" in patch
        assert "+new1" not in patch
        assert "+new2" not in patch

    def test_select_one_addition_and_one_deletion(self) -> None:
        hunk = _make_hunk()
        # select -old1 (1) and +new1 (3)
        patch = build_line_patch("f.py", hunk, {1, 3})
        _, old_count, _, new_count = _parse_hunk_header(patch)
        # output: context1, -old1, old2(ctx), +new1, context2
        assert old_count == 4  # 2 ctx + 1 converted ctx + 1 deletion
        assert new_count == 4  # 2 ctx + 1 converted ctx + 1 addition
        assert "-old1" in patch
        assert " old2" in patch
        assert "+new1" in patch
        assert "+new2" not in patch

    def test_select_single_addition(self) -> None:
        hunk = _make_hunk()
        # select only +new1 (3)
        patch = build_line_patch("f.py", hunk, {3})
        _, old_count, _, new_count = _parse_hunk_header(patch)
        # output: context1, old1(ctx), old2(ctx), +new1, context2
        assert old_count == 4  # 2 ctx + 2 converted ctx
        assert new_count == 5  # 4 ctx + 1 addition
        assert "+new1" in patch
        assert "+new2" not in patch
        assert " old1" in patch
        assert " old2" in patch

    def test_select_single_deletion(self) -> None:
        hunk = _make_hunk()
        # select only -old1 (1)
        patch = build_line_patch("f.py", hunk, {1})
        _, old_count, _, new_count = _parse_hunk_header(patch)
        # output: context1, -old1, old2(ctx), context2
        assert old_count == 4  # 2 ctx + 1 deletion + 1 converted ctx
        assert new_count == 3  # 2 ctx + 1 converted ctx
        assert "-old1" in patch
        assert " old2" in patch
        assert "+new1" not in patch
        assert "+new2" not in patch

    def test_header_recalculation(self) -> None:
        hunk = _make_hunk()
        # select -old2 (2) and +new2 (4)
        patch = build_line_patch("f.py", hunk, {2, 4})
        _, old_count, _, new_count = _parse_hunk_header(patch)
        # output: context1, old1(ctx), -old2, +new2, context2
        # old_count = context1 + old1(ctx) + -old2 + context2 = 4
        # new_count = context1 + old1(ctx) + +new2 + context2 = 4
        assert old_count == 4
        assert new_count == 4

    def test_context_lines_always_present(self) -> None:
        hunk = _make_hunk()
        # empty selection - no changed lines selected
        patch = build_line_patch("f.py", hunk, set())
        assert " context1" in patch
        assert " context2" in patch
        # unselected deletions become context
        assert " old1" in patch
        assert " old2" in patch

    def test_patch_ends_with_trailing_newline(self) -> None:
        hunk = _make_hunk()
        patch = build_line_patch("f.py", hunk, {1, 3})
        assert patch.endswith("\n")

    def test_patch_has_valid_diff_headers(self) -> None:
        hunk = _make_hunk()
        patch = build_line_patch("some/path.py", hunk, {1, 2, 3, 4})
        assert patch.startswith("diff --git a/some/path.py b/some/path.py\n")
        assert "\n--- a/some/path.py\n" in patch
        assert "\n+++ b/some/path.py\n" in patch


class TestReversePatch:
    def _reverse_lines(self, patch: str) -> list[str]:
        """Split reversed patch into lines for assertion helpers."""
        return patch.splitlines()

    def test_file_headers_swapped(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        rev = reverse_patch(patch)
        assert "\n--- b/hello.py\n" in rev
        assert "\n+++ a/hello.py\n" in rev
        assert "\n--- a/hello.py\n" not in rev
        assert "\n+++ b/hello.py\n" not in rev

    def test_addition_becomes_deletion(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        rev = reverse_patch(patch)
        assert "\n-import sys\n" in rev
        assert "\n+import sys\n" not in rev

    def test_deletion_becomes_addition(self) -> None:
        hunk = parse_diff(DELETIONS_ONLY_DIFF)[0]
        patch = build_hunk_patch("old.py", hunk)
        rev = reverse_patch(patch)
        assert "\n+removed one\n" in rev
        assert "\n+removed two\n" in rev
        assert "\n+removed three\n" in rev
        assert "\n-removed one\n" not in rev

    def test_context_lines_unchanged(self) -> None:
        hunk = Hunk(
            header="@@ -1,3 +1,3 @@",
            lines=[" context", "-old line", "+new line", " more context"],
            start_old=1,
            count_old=3,
            start_new=1,
            count_new=3,
        )
        patch = build_hunk_patch("mixed.py", hunk)
        rev = reverse_patch(patch)
        assert "\n context\n" in rev
        assert "\n more context\n" in rev

    def test_hunk_header_counts_swapped(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        rev = reverse_patch(patch)
        # original: @@ -1,3 +1,4 @@ -> reversed: @@ -1,4 +1,3 @@
        so, co, sn, cn = _parse_hunk_header(rev)
        assert so == hunk.start_new
        assert co == hunk.count_new
        assert sn == hunk.start_old
        assert cn == hunk.count_old

    def test_diff_git_line_unchanged(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        rev = reverse_patch(patch)
        first_line = rev.splitlines()[0]
        assert first_line == "diff --git a/hello.py b/hello.py"

    def test_addition_only_patch_reversed(self) -> None:
        hunk = parse_diff(ADDITIONS_ONLY_DIFF)[0]
        patch = build_hunk_patch("new.py", hunk)
        rev = reverse_patch(patch)
        # all + become -, counts swap: @@ -0,0 +1,3 @@ -> @@ -1,3 +0,0 @@
        so, co, sn, cn = _parse_hunk_header(rev)
        assert so == 1
        assert co == 3
        assert sn == 0
        assert cn == 0
        assert "\n-line one\n" in rev
        assert "\n-line two\n" in rev
        assert "\n-line three\n" in rev
        assert "+" not in rev.split("@@")[-1]

    def test_deletion_only_patch_reversed(self) -> None:
        hunk = parse_diff(DELETIONS_ONLY_DIFF)[0]
        patch = build_hunk_patch("old.py", hunk)
        rev = reverse_patch(patch)
        # all - become +, counts swap: @@ -1,3 +0,0 @@ -> @@ -0,0 +1,3 @@
        so, co, sn, cn = _parse_hunk_header(rev)
        assert so == 0
        assert co == 0
        assert sn == 1
        assert cn == 3
        assert "\n+removed one\n" in rev
        assert "\n+removed two\n" in rev
        assert "\n+removed three\n" in rev
        # no deletion lines in body
        body = rev.split("@@")[-1]
        assert "-" not in body

    def test_trailing_newline_preserved(self) -> None:
        hunk = parse_diff(SINGLE_HUNK_DIFF)[0]
        patch = build_hunk_patch("hello.py", hunk)
        rev = reverse_patch(patch)
        assert rev.endswith("\n")
