# postup G1: absorbed autopilot data layer (durable hooks + versioned state contract)

<!-- requirements; migrated from PRD 00069 flat file -->

## Overview

### Problem Statement
pidash's autopilot state is written by concurrently running hook processes with unlocked read-modify-write cycles — a live lost-update/data-loss class (00049) — and read through an implicit, unversioned mirror of the autopilot skill's `state.json` schema that drifts and breaks after the fact (00059). postup absorbs pidash; this PRD lands the absorbed data layer first (needs only the gem skeleton) so the durability fix does not wait behind the frontend chain: hook state writes durable and serialized from day one, and the state schema an explicit, versioned, contract-tested model.

### Target Users
The autopilot machinery writing state via installed hooks; PRD 00070's cycle views reading it; the solo developer running `postup hooks install`.

### Success Metrics
- Concurrent-writer regression test proves two interleaved read-modify-write cycles lose neither update.
- A deliberate state-shape change breaks the contract test (drift is caught in CI, not in use).
- `postup hooks install` is idempotent and preserves the existing order of hook-array entries, including non-dict entries.
- The 00049/00059 obligations are each traceable to a passing test or doc artifact in this PRD.

## Functional Decomposition

### Capability: Durable hook layer
Ported hook scripts that cannot lose updates.

#### Feature: State-write serialization
- **Description**: A flock-based lock around every state read-modify-write, with atomic replace underneath.
- **Inputs**: Hook payloads (Claude Code hook events); the autopilot state file.
- **Outputs**: Serialized, durable state writes.
- **Behavior**: A `with_state_lock` context manager (fcntl.flock on a sidecar lock file) wraps the full load→mutate→replace sequence; `pybase.filesystem.atomic_write` (fsync-before-replace) is the write primitive. Writes to Claude settings during install fsync before replace (00049 #111 obligation).

#### Feature: Hook script port
- **Description**: Port pidash's hook scripts into postup, born durable.
- **Inputs**: pidash sources: `hooks/update_tasks.py`, `sync_agent_return.py`, `set_attention.py`, `clear_attention.py`, `cleanup_session.py`, `session.py`.
- **Outputs**: `src/tools/postup/hooks/` equivalents; the four state-mutating hooks hold the lock for their full read-modify-write; `cleanup_session` (per-session mirror file only, no shared state) stays lock-free per 00049.
- **Behavior**: Behavior parity with pidash's hooks plus the durability guarantees; hook scripts stay standalone-executable (they run as installed copies outside the package).

### Capability: Hook lifecycle
Installing and inspecting the machinery.

#### Feature: hooks install
- **Description**: `postup hooks install` deploys the hook entries into Claude Code settings.
- **Inputs**: Target settings file (hooks arrays); postup's hook script paths.
- **Outputs**: `CommandResult`; updated settings with postup entries.
- **Behavior**: Preserves the original order of existing entries including non-dict entries (00049 #112); idempotent (re-running does not duplicate); supersedes previously installed pidash hook entries for the same events (the migration path — installed copies under `~/.claude/hooks/` are replaced by the durable ones); `hooks` Click subgroup uses `@click.pass_context` and one shared row-rendering helper (00049 #113/#114 lessons).

#### Feature: hooks status
- **Description**: `postup hooks status` shows what is installed vs expected.
- **Inputs**: Settings file; installed hook copies.
- **Outputs**: `CommandResult` with per-hook installed/missing/outdated rows rendered once via the shared helper.
- **Behavior**: Read-only; renders through `console.report_result` without double-rendering.

### Capability: Versioned autopilot state contract
The reader side, made explicit.

#### Feature: State model
- **Description**: The autopilot `state.json` parsed via an explicit, versioned pydantic model.
- **Inputs**: `state.json` payloads written by the autopilot skill (and the hooks above).
- **Outputs**: Typed state objects for 00070's views; loud errors otherwise.
- **Behavior**: `schema_version` field required; an unknown/newer version yields a clear message, never a silent misparse (00059).

#### Feature: Contract tests and shared-contract doc
- **Description**: Pin the model to representative payloads and document the contract.
- **Inputs**: Representative `state.json` payloads (the shapes the autopilot skill writes today).
- **Outputs**: Contract test suite; a doc note (postup docs or `dev/local/specs/`) naming the schema as the shared contract with the autopilot skill and how to bump `schema_version`.
- **Behavior**: A drift in field shape breaks the contract test here instead of the TUI in use; writer-side coordination (autopilot skill referencing this model) stays an out-of-repo follow-up note per 00059's nice-to-have.
