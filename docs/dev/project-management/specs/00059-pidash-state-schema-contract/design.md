# pidash: versioned state schema + snapshot layout gate

<!-- design; migrated from PRD 00059 flat file -->

## Implementation

### Module: pidash.tui.state (+ snapshot tests)
- **Location**: `src/tools/pidash/tui/state.py`, `tests/tools/pidash/` (snapshot + contract tests)
- **Responsibility**: a versioned, contract-tested state model; snapshot-gated layouts.
- **Exports**: versioned `State` model; contract + snapshot test suites

### Dependencies
- No dependency. (The writer-side coordination touches the external autopilot skill and is noted, not blocking.)
