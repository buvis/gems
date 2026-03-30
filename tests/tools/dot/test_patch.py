from __future__ import annotations

from dot.tui.patch import Hunk, parse_diff


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
