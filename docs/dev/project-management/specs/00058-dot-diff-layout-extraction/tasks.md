# dot: extract a pure DiffLayout model from the diff widget

<!-- tasks; migrated from PRD 00058 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] Create `DiffLayout` with the hunk/offset/clamp/visible-region logic lifted out of `diff_view.py` (no deps) — Acceptance: unit tests (no Textual) cover all six historical edge cases.

### Phase 1: Core
- [ ] Rewrite `DiffView` to render from `DiffLayout`; remove inline arithmetic (depends on: Phase 0) — Acceptance: existing diff-view tests pass; no offset math remains in the widget.
