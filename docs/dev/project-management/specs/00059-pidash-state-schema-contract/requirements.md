# pidash: versioned state schema + snapshot layout gate

<!-- requirements; migrated from PRD 00059 flat file -->

## Problem

The pidash TUI is the repo's biggest fix magnet (`tui/app.py` 19 fixes across 26 commits; pidash 15.1 fixes/kloc) for two structural reasons: (1) layout is verified by eyeballing a live TUI, so spacing/color/visibility regressions ship and get patched one at a time (a 19-fix chain, `1c6d675`…`dd263ed`); (2) `tui/state.py` is an **implicit mirror** of the external autopilot skill's `state.json` schema, so when the skill changes the JSON, pidash drifts and `state.py` gets re-fixed after the fact (`19286fb`, `77d451e`, `8a2ee80`). There is no shared, versioned contract between the writer (the autopilot skill) and the reader (pidash).

## Solution

Two moves: make the state schema an explicit, versioned pydantic model that is the single source of truth for the reader (and contract-tested against sample payloads the autopilot skill produces), and adopt Textual snapshot tests as the default acceptance gate for any pidash layout change so visual regressions fail in CI instead of in use.

## Requirements

### Must have
- `tui/state.py` parses via an explicit, **versioned** pydantic model (a `schema_version` field); an unknown/newer version is handled with a clear message rather than silently mis-parsing.
- A contract test pins the model against representative `state.json` payloads (the shapes the autopilot skill writes), so a drift breaks a test here instead of the TUI in use.
- Textual snapshot tests cover the main pidash layouts and are the acceptance gate for layout changes on the canonical env (they auto-skip elsewhere per AGENTS.md). Extend to the genuinely uncovered churned surfaces: the attention banner and dedicated pipeline/progress states (the multi-session sidebar is already snapshotted by `test_multi_session_with_many_sessions`).
- A short doc note (pidash docs or `dev/local/specs/`) naming the state schema as the shared contract with the autopilot skill and how to bump `schema_version`.

### Nice to have
- Coordinate the writer side: reference the pydantic model (or a derived JSON schema) from the autopilot skill so both sides share one definition. (Out-of-repo; note as a follow-up if it can't land here.)

## Success Criteria

- State-schema drift is caught by a contract test, not by a user.
- Layout changes go through snapshot review; pidash tests green.
