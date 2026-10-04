# dot TUI: refresh git-secret status so changed secrets show (issue #92)

<!-- design; migrated from PRD 00046 flat file -->

## Implementation

### Module: dot.tui.git_ops
- **Location**: `src/tools/dot/tui/git_ops.py`
- **Responsibility**: produce a git status that reflects freshly-hidden secrets.
- **Exports**: `GitOps.status()` (add the guarded hide step)

### Dependencies
- No dependencies. (Subsumed later by 00053's shared git-ops service; ship the fix now — #92 is 3 months old.)
