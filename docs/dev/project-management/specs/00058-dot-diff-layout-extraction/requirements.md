# dot: extract a pure DiffLayout model from the diff widget

<!-- requirements; migrated from PRD 00058 flat file -->

## Problem

dot's diff/scroll viewport math lives as index arithmetic inside the Textual widget (`src/tools/dot/tui/widgets/diff_view.py`), and every edge case has shipped as a fresh production bug: 6 scroll/offset fixes across three days (chain `4abf1c3`…`9d06d0a`) — headerless diff offsets, single-hunk anchoring, revealing past the last hunk, clamping restored indices. The file carries 9 fixes across 18 commits. The root flaw is that the hunk→line-offset mapping, clamping, and visible-region logic can only be tested by driving a live Textual widget, so edges are found by hand at runtime instead of by a unit test.

## Solution

Extract a pure `DiffLayout` model that owns the coordinate math — hunk→offset map, index clamping, visible-region computation — as plain data with no Textual dependency. The widget becomes a thin renderer that asks `DiffLayout` where things are. The math gets unit tests covering every edge that previously shipped as a bug.

## Requirements

### Must have
- A `DiffLayout` (pure Python, no Textual import) computing: hunk→line-offset map, clamped scroll/reveal indices, and the visible region for a given viewport.
- `DiffView` renders from `DiffLayout` and no longer does offset arithmetic inline.
- Unit tests (no Textual) cover: headerless diff, single hunk, reveal past the last hunk, clamp at both ends, empty diff — i.e. the exact cases behind `4abf1c3`, `5b8cee5`, `66ada63`, `73462f1`, `24474a7`, `9d06d0a`.
- Existing diff-view behavior preserved (characterize with the current tests first).

### Nice to have
- Reuse `DiffLayout` for any other diff surface if one exists.

## Success Criteria

- The diff coordinate math is unit-tested without a TUI; the historical scroll bugs are covered.
- dot tests green; `diff_view.py` is a thin renderer.
