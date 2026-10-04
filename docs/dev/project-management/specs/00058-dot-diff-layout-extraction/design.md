# dot: extract a pure DiffLayout model from the diff widget

<!-- design; migrated from PRD 00058 flat file -->

## Implementation

### Module: dot.tui.widgets.diff_layout
- **Location**: `src/tools/dot/tui/widgets/diff_layout.py` (new), `diff_view.py` (renders from it)
- **Responsibility**: all diff coordinate math, testable without a TUI.
- **Exports**: `DiffLayout` with `offset_of(hunk)`, `clamp(index)`, `visible_region(viewport)`

### Dependencies
- No dependency. Independent of the git-ops unification (00053).
