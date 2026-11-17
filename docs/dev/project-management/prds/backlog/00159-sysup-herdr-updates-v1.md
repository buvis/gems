---
catchup: force
eligibility: test -f docs/dev/project-management/prds/done/00158-sysup-herdr-snapshots-v1.md
default_model: opus
model_tier_rationale: Async update ordering, deadlines, restart recovery and no-retry mutation rules require concurrency reasoning.
---

# sysup observable Herdr updates

Source: `docs/dev/project-management/intake/processed/00157-sysup-herdr-update-orchestration/discovery.md` and sibling decisions.md.
Depends on PRDs 00157 (observation) and 00158 (snapshots/lock).
Reference: `docs/dev/project-management/spikes/herdr-update-bridge/RESULTS.md`.

## Overview

### Problem Statement
A successful Herdr CLI dispatch does not prove an update completed. Coordinate
supported app/core actions with fresh observations and preserved source bytes.
Herdr owns downloads and installation; hmod retains community-mod ownership.

### Target Users
The solo developer opting into sysup-managed Herdr update checks and restarts.

### Success Metrics
Fake-process tests never report completion on dispatch or connection loss alone.
Default sysup configuration performs no Herdr update/restart. Opt-in restart
verifies the captured target after reconnection and preserves pre-update sources.
No test changes installed software or the user's running window.

## Functional Decomposition

### Capability: Observable update workflow
Drive supported actions using one shared service with explicit outcomes.

#### Feature: Fresh checks and core completion
- **Description**: Check for updates and optionally update a Herdr-owned core.
- **Inputs**: Selected home, fresh observation client, snapshot store/home lock;
  update_core=true, restart=false, timeout_seconds=120 defaults on the opt-in entry.
  These are `with:` inputs of the capability; the entry-level `timeout` field
  is not used by `use:` entries.
- **Outputs**: Operation report distinguishing unchanged, requested, running,
  completed, deferred, failed and unavailable; adapters return existing results.
- **Behavior**: Acquire the PRD 00158 home lock before observing or mutating;
  hold through the operation, release on every exit. Use one monotonic operation
  deadline; clamp each subprocess/probe to remaining time. Never launch a closed
  app. Require a fresh initial sample. If checks=false, report unsupported.
  If checking=true, wait for it to settle before requesting another check.
  Because checked uses Unix seconds, wait until prior checked is older than
  the current wall-clock second (null needs no wait), then dispatch exactly one
  herdr-app do app.check_updates. Require a fresh sample with checking=false
  and nonnull checked greater than prior checked (or at least dispatch's
  wall-clock second if prior was null). A failed check resets checked to null;
  null while checking=false is failed only after checking=true was observed
  after dispatch. Otherwise keep waiting for fresh success until the deadline;
  an unchanged pre-dispatch state cannot prove a failed or completed check.
  Clock anomalies consume the deadline and end unavailable, never a busy loop.
  Capture all shipped source assets before any core/app installation dispatch;
  unreadable inventory, storage refusal or partial capture blocks that mutation.
  For core.ready, capture the exact target. Nonnull core.managed means defer to
  its named package manager, never dispatch. If core.updating=true, observe the
  existing operation rather than starting another; no identifiable target means
  unavailable, never inferred completion. With update_core=false,
  report offered core update as deferred. Otherwise dispatch app.update_core
  once and observe until core.version equals the target, updating=false and
  error=null. A nonnull error fails. No offered target means no core mutation;
  report observed state, without asserting global newest-version status.

#### Feature: Explicit app restart and recovery
- **Description**: Apply only an observed ready app version under opt-in policy.
- **Inputs**: Fresh app.ready target, app.updates support, restart flag, source snapshots.
- **Outputs**: Verified completed target, deferred restart, failed or unavailable.
- **Behavior**: Finish core handling before any app restart; do not restart while
  the core is updating or after an unresolved core failure. If app.ready is null,
  report no ready update; do not treat a still-downloading release as installed.
  If restart=false, retain attention for a ready app. If app.updates=false, do
  not dispatch. Capture all shipped sources immediately before restart and
  reobserve target; changed target requires re-evaluation within the deadline.
  Dispatch herdr-app do app.update once. Never kill/relaunch the app independently
  or terminate terminals. Reacquire fresh bridge replies after disconnect until
  the deadline; success requires app.version exactly equal to captured target.
  Another version is unresolved review, not success by guessed ordering.
  Capture the post-restart sources and retain pre/post identities in the report.
  A post-capture failure reports completed installation plus failed preservation;
  do not incorrectly claim the update was undone. Snapshot identities are
  observations, not proof of clone ancestry or exact shipped provenance.
  Restart may trigger Herdr's own core updater even when update_core=false;
  that flag controls sysup dispatch only. Reobserve core state after restart;
  report any running/error state separately rather than claiming all complete.

#### Feature: Ambiguous dispatch handling
- **Description**: Prevent duplicate mutations after uncertain IPC outcomes.
- **Inputs**: Action dispatch result, captured target, subsequent fresh samples.
- **Outputs**: Observed outcome with diagnostic and any completed substeps.
- **Behavior**: A timeout/disconnect after dispatch triggers observation only,
  never automatic resend. An explicit CLI rejection fails with its reason.
  Timeout, absent bridge, unsupported schema and unexpected target leave
  attention. Record which action was attempted and which source snapshots
  exist, but never resume an old mutation automatically in a later sysup run.
  Subsequent runs start from fresh state and current readiness.

### Capability: sysup integration
Preserve the runner and attention lifecycle.

#### Feature: Disabled-by-default capability
- **Description**: Add herdr-updates using the herdr-update capability.
- **Inputs**: Existing selection, dry-run and capability inputs.
- **Outputs**: StepResult values; shared CommandHerdr update returns CommandResult.
- **Behavior**: Register a macOS-only default entry at order 77, enabled=false;
  preserve hmod at 78 and clone audit at 79. Validate boolean policies strictly
  and finite positive timeout; an invalid input gives one failed StepResult
  before any observation, with no fallback to a default. Report
  completed/unchanged and "no ready update" as ok; deferred and unsupported
  (checks=false) as success=True/status=warned; unavailable, requested or
  running at the deadline, and an unexpected version after restart as
  success=False/status=unknown;
  failed as success=False/status=failed. Mixed results retain failures.
  Dry-run performs no observation/capture/dispatch. The group option --dry-run
  does not reach subcommands today: pass it to `sysup herdr update`, which then
  only reports what it would do. Normal runs launch no agents
  or clone checks and install no bridge. Expose sysup herdr update through the
  same service with restart default off, never reimplement logic per interface.
  Both adapters receive the resolved herdr.budget_bytes from PRD 00158 through
  the selected configuration context. Wire the runner to supply that context;
  do not reload default config inside the capability or lose --config overrides.
  Existing capabilities keep receiving only their `with:` inputs
  (`test_use_passes_with_inputs` in `tests/tools/sysup/test_runner.py` stays green).

## Structural Decomposition

### Repository Structure

```text
src/tools/sysup/herdr/update.py                # shared state machine
src/tools/sysup/capabilities/herdr_update.py   # StepResult adapter
src/tools/sysup/capabilities/__init__.py       # registry
src/tools/sysup/runner.py                      # resolved configuration context
src/tools/sysup/commands/herdr.py              # shared facade from 00157
src/tools/sysup/cli.py                         # lazy command adapter
src/tools/sysup/default.yaml                   # disabled opt-in entry
tests/tools/sysup/test_herdr_update.py          # fake clock/process state cases
tests/tools/sysup/test_herdr_update_integration.py # attention and dry-run
tests/tools/sysup/test_default_config.py        # ordering/default assertions
docs/source/tools/sysup.rst                    # policies and recovery
CHANGELOG.md                                  # unreleased entry
```

### Module: Update service
- **Maps to capability**: Observable update workflow
- **Responsibility**: Serialize, capture, dispatch once and observe outcomes.
- **Exports**: HerdrUpdateService.
- New symbols: `HerdrUpdateService`, `src/tools/sysup/herdr/update.py`, `tests/tools/sysup/test_herdr_update.py`.

### Module: sysup adapters
- **Maps to capability**: sysup integration
- **Responsibility**: Share service semantics across capability and command interfaces.
- **Exports**: HerdrUpdate capability; existing CommandHerdr facade.
- New symbols: `HerdrUpdate`, `src/tools/sysup/capabilities/herdr_update.py`, `tests/tools/sysup/test_herdr_update_integration.py`, `src/tools/sysup/commands/herdr.py` (from PRD 00157).

## Dependency Graph

### Foundation Layer (Phase 0)
- **Update service**: Depends on [PRD 00157 observation, PRD 00158 store and lock].

### Core Layer (Phase 1)
- **sysup adapters**: Depends on [Update service].

### Integration Layer (Phase 2)
- **sysup adapters** (default entry and reference docs): Depends on [Update service]; preserve PRD 00156 audit if present.

## Implementation Phases

### Phase 0: Foundation
**Goal**: Make completion an observed fact.

**Tasks**:
- [ ] Implement checks/core state machine with injected processes, storage and clocks (depends on: PRDs 00157, 00158). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_update.py` proves check freshness, managed-core refusal, captured targets, pre-mutation capture and no duplicate dispatch.
- [ ] Add opt-in app restart/recovery (depends on: previous task). Acceptance: the same focused test command covers disconnect, target equality, changed targets, deadline exhaustion and failed post-capture with truthful partial outcomes.

**Exit Criteria**: No completed outcome is inferred from an action's exit code.

### Phase 1: Core
**Goal**: Integrate consistent outcomes with attention and commands.

**Tasks**:
- [ ] Add capability, shared facade operation, CLI adapter and disabled config entry (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_update_integration.py tests/tools/sysup/test_default_config.py` proves defaults, exact result mapping, attention persistence/clearing, mixed failures and dry-run isolation. Preserve hmod and audit ownership/order; recheck the premise before editing and report if it changed.

**Exit Criteria**: Both interfaces drive the same service; restart remains opt-in.

### Phase 2: Integration
**Goal**: Document operation and recovery without runtime approval gates during build.

**Tasks**:
- [ ] Document setup dependency, enable/restart policies, deferred package-managed cores, storage failure and uncertain-dispatch recovery; add changelog (depends on: Phase 1). Acceptance: `uv run sphinx-build -b html docs/source docs/build/html` succeeds.

**Exit Criteria**: `uv run pytest` and `uv run mypy src/lib/ src/tools/` pass with normal platform snapshot skips. Use fixtures, not a real update.

## Test Strategy

### Critical Scenarios
- **Happy path**: New check timestamp, ready owned core, running transition, target version → completion only after fresh final state.
- **Clock/order**: Same-second prior check, backwards clock, pre-dispatch sample, null failed-check time, existing background operation → bounded correct result without duplicate mutation.
- **Restart**: Policy off, no ready update, disappearing bridge, reconnect to wrong version → deferred/no-op/unavailable/review respectively.
- **Failures**: Busy lock, capacity refusal, partial capture, process rejection, timeout, core error, post-update capture failure → accurate outcome and retained attention.
- **Ownership**: Package-managed core and community mods remain under their existing owners; live clones never change.
- **Configuration**: --config/--config-dir budget overrides reach both capability and facade; no fallback reload silently changes admission.

## Risks

- **Same-user races**: sysup's lock cannot stop Herdr's automatic updater or UI actions; reobserve and expose mismatches instead of assuming exclusive ownership.
- **Native proof limit**: The spike proves transport/lifecycle, not real version-changing updates; deterministic state-machine tests must cover those transitions.
- **External restarts**: Snapshots cover sysup-observed transitions only, never every update initiated elsewhere.
