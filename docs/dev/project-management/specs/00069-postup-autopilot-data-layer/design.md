# postup G1: absorbed autopilot data layer (durable hooks + versioned state contract)

<!-- design; migrated from PRD 00069 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/postup/
├── hooks/                       # Maps to: Durable hook layer
│   ├── session.py               # ported write_json_atomic/mirror helpers + NEW with_state_lock (no lock primitive exists in pidash today)
│   ├── update_tasks.py
│   ├── sync_agent_return.py
│   ├── set_attention.py
│   ├── clear_attention.py
│   └── cleanup_session.py
├── domain/
│   └── autopilot_state.py       # Maps to: State model (schema_version)
├── commands/
│   └── hooks/
│       ├── install.py           # Maps to: hooks install (CommandHooksInstall)
│       └── status.py            # Maps to: hooks status (CommandHooksStatus)
└── adapters/cli.py              # + hooks subgroup (@click.pass_context)
tests/tools/postup/              # concurrent-writer, install-order, contract tests
```

### Module: postup.hooks
- **Maps to capability**: Durable hook layer
- **Responsibility**: Hook-event handling with serialized, durable state writes; standalone-executable scripts.
- **Exports**:
  - `with_state_lock(state_path)` - flock context manager
  - the five hook entry points

### Module: postup.domain.autopilot_state
- **Maps to capability**: Versioned autopilot state contract
- **Responsibility**: The single source of truth for reading autopilot state.
- **Exports**:
  - `AutopilotState` (versioned, `schema_version`) - typed model
  - `load_state(path)` - loud on unknown versions

### Module: postup.commands.hooks
- **Maps to capability**: Hook lifecycle
- **Responsibility**: Install/status orchestration returning `CommandResult`.
- **Exports**:
  - `CommandHooksInstall`, `CommandHooksStatus`

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00063 (skeleton) and 00041 (`atomic_write`) must be in `done/`.

- **domain.autopilot_state + hooks.session (lock primitive)**: no internal dependencies — built first.

### Core Layer (Phase 1)
- **hooks scripts (four state-mutating + cleanup_session)**: depends on [hooks.session, autopilot_state]

### Integration Layer (Phase 2)
- **commands.hooks + CLI subgroup**: depends on [hooks scripts]

## Test Strategy

### Critical Scenarios
- **Happy path**: hook event → locked RMW → atomic replace → Expected: state updated, lock released, mirror files untouched by lock.
- **Edge case**: two writers interleaved; install run twice; settings with pre-existing non-dict entries → Expected: both updates present; no duplicates; original entry order preserved.
- **Error case**: `state.json` with unknown `schema_version` / corrupted JSON → Expected: clear message (which version, what to do), no silent misparse, no traceback.

## Risks

- **Open decision (design): exact autopilot state source paths** (per-repo autopilot `state.json`, per-session mirror files) — confirm from pidash's `tui/state.py`/`hooks/session.py` while designing; the discovery flags this explicitly.
- **Coexistence window with pidash (until 00070)**: both tools exist; the installed hook copies are the live machinery — postup's installer supersedes pidash's entries so the durable versions run even while pidash source remains.
- **Writer-side coordination is out-of-repo**: the autopilot skill writing `state.json` lives outside gems; the doc note is the contract until the skill references the model (follow-up, per 00059 nice-to-have).
- **Concurrency test flakiness**: use deterministic interleaving (injected sync points), not sleeps.
