---
design: run
default_model: opus
model_tier_rationale: concurrency and equivalence obligations in maintenance, pruning and scheduling
eligibility: test -f docs/dev/project-management/prds/done/00153-bim-tiromex-ingest-v1.md
---

# bim tx maintenance, scheduling and shared interfaces

Source: [Discovery 00149](docs/dev/project-management/intake/processed/00149-merge-klyreon-into-bim/discovery.md); adjacent port-plan.md supplies the approved inventory. Discovery overrides older examples. Part 5 of 6; explicit discovery numbering is retained.

Grounding: `plan_lifecycle` at `src/tools/klyreon/maintain/rules.py:52-62` explicitly advances one step; `plan_assent` at `src/tools/klyreon/maintain/rules.py:91-99` supplies the unchanged assent predicate.

## Overview

### Problem Statement
Finish the operational port: maintain tiromex, schedule unattended runs and route interfaces through shared commands. Covers M25–M30 and the maintenance portion of M10; requires 00153 and its prerequisites complete.

### Target Users
The vault owner and unattended agents using bim. Tests use scratch vaults and isolated HOME/XDG_STATE_HOME; never the private vault.

### Success Metrics
`uv run pytest tests/tools/bim/tx/test_maintain.py tests/tools/bim/tx/test_prune.py tests/tools/bim/tx/test_schedule.py tests/tools/bim/tx/test_interfaces.py` proves the second maintain run changes no vault content/HEAD, external backlinks prevent pruning, and CLI/serve/TUI share results.

## Functional Decomposition

### Capability: Deterministic maintenance
#### Feature: Lint, promote and synchronize
- **Description**: Run the five maintenance steps in the approved order.
- **Inputs**: Tiromex graph and ported lifecycle/assent predicates; 00153 transaction helpers.
- **Outputs**: Scoped transitions, members blocks and aggregate journal.
- **Behavior**: Order: lint, lifecycle promotion, assent transitions, MOC sync, prune detection. Port exact predicates from source rules: fleeting→literature needs source plus link; literature→evergreen needs at least two distinct sources including own; tentative→accepted needs at least two distinct non-own sources and no open disagreement. Do not reset processed, bump updated on promotion or write rejected. Finish eligible lifecycle steps in this invocation, each as its own commit, so the second run is a no-op even for a fleeting note qualifying for evergreen. Apply tx rules only to concept/index/tx-run kinds, preserving plain notes. Skip unparseable graph entries but report them through lint. Rewrite only sorted tx:members blocks, never prose; malformed MOCs are reported/skipped. No-op maintain writes last_maintain only in state, never a journal. Dry-run writes nothing, including last_maintain.
#### Feature: Conservative pruning
- **Description**: Keep pruning opt-in and protect every outside backlink.
- **Inputs**: pruning_enabled=false, prune_window_days=365, graph and external inbound-link scan.
- **Outputs**: Candidate report or one grouped scoped prune commit.
- **Behavior**: Retain source prune predicates and delivered-as exemption; exclude own-source evidence from corroboration. A note with any inbound link outside tiromex cannot be a candidate. Outside notes may be scanned locally solely to detect backlinks; no content enters prompts or tx edits. Recheck candidate eligibility, dirty status and inbound links immediately before deletion; if changed, skip/report. Retain doubt history while removing only target fields that name a pruned note. Use 00153 scoped commit/identity/rollback helpers for all writes, preserve dirty and plain agent notes.
### Capability: Scheduled and shared execution
#### Feature: Managed schedule
- **Description**: Install/status/uninstall the existing platform schedulers with renamed artifacts.
- **Inputs**: --at, captured PATH, backend unattended policy and artifact hash.
- **Outputs**: net.buvis.bim.tx launchd job or # bim-tx-managed crontab entry.
- **Behavior**: Run bim tx ingest; bim tx maintain with semicolon so maintain follows failed ingest. macOS logs stdout/stderr to ~/Library/Logs/bim/tx.log; Linux also retains output using the existing platform convention refined in design. Reuse source hash checks: changed/unowned artifacts are not overwritten or deleted. Capture PATH at install; reject generic backend scheduling unless unattended:true. Do not install a real job during tests.
#### Feature: All-interface command adapters
- **Description**: Expose the same CommandResult operations through CLI, serve actions and TUI.
- **Inputs**: Shared composition and action handlers; tx command parameters.
- **Outputs**: Equivalent command outcomes, surfaced through each interface.
- **Behavior**: At minimum status/validate/ingest/maintain must be registered in ACTION_HANDLERS and accessible in TUI/WebUI. Keep every additional new action on the same command seam rather than duplicating business logic. Honor current HTTP token/auth/TrustedHost/path confinement; never let a request select arbitrary filesystem roots or generic executable argv. Pass dry-run/backend limits through validated params. UI adapters render results only; all decisions remain in commands.

## Structural Decomposition

### Repository Structure
```text
src/tools/bim/commands/tx/maintain.py
src/tools/bim/commands/tx/schedule.py
src/tools/bim/commands/tx/shared/          # rules, graph, pruning, schedule
src/tools/bim/commands/serve/_actions.py
src/tools/bim/tui/tx.py
tests/tools/bim/tx/                       # focused suites below
CHANGELOG.md
docs/source/tools/bim.rst
src/tools/bim/SKILL.md
src/tools/bim/tx_cli.py
src/tools/bim/commands/tx/status.py
src/tools/bim/dependencies.py
src/tools/bim/manifest.toml
src/tools/bim/tui/query.py
tests/tools/bim/test_serve_actions.py
tests/tools/bim/test_serve_security.py
```

### Module: Maintenance
- **Maps to capability**: Deterministic maintenance
- **Location**: `src/tools/bim/commands/tx/maintain.py`, `src/tools/bim/commands/tx/shared/graph.py`, `src/tools/bim/commands/tx/shared/rules.py`, `src/tools/bim/commands/tx/shared/moc_sync.py`, `src/tools/bim/commands/tx/shared/prune.py`, `src/tools/bim/commands/tx/shared/sweep.py`, `tests/tools/bim/tx/test_maintain.py`, `tests/tools/bim/tx/test_prune.py`, `src/tools/bim/commands/tx/status.py`, `src/tools/bim/commands/tx/shared/state.py`, `src/tools/bim/commands/tx/shared/settings.py`, `src/tools/bim/commands/tx/shared/journal.py`
- **Responsibility**: Maintenance graph, transition planners, member sync, prune report/apply.
- **Exports**: Maintenance graph, transition planners, member sync, prune report/apply.
New symbols: `src/tools/bim/commands/tx/maintain.py`, `src/tools/bim/commands/tx/shared/graph.py`, `src/tools/bim/commands/tx/shared/rules.py`, `src/tools/bim/commands/tx/shared/moc_sync.py`, `src/tools/bim/commands/tx/shared/prune.py`, `src/tools/bim/commands/tx/shared/sweep.py`, `tests/tools/bim/tx/test_maintain.py`, `tests/tools/bim/tx/test_prune.py`
### Module: Scheduler
- **Maps to capability**: Scheduled and shared execution
- **Location**: `src/tools/bim/commands/tx/schedule.py`, `src/tools/bim/commands/tx/shared/schedule/__init__.py`, `src/tools/bim/commands/tx/shared/schedule/launchd.py`, `src/tools/bim/commands/tx/shared/schedule/cron.py`, `src/tools/bim/commands/tx/shared/schedule/installer.py`, `tests/tools/bim/tx/test_schedule.py`
- **Responsibility**: Platform artifact render/install/status/uninstall with ownership hashes.
- **Exports**: Platform artifact render/install/status/uninstall with ownership hashes.
New symbols: `src/tools/bim/commands/tx/schedule.py`, `src/tools/bim/commands/tx/shared/schedule/__init__.py`, `src/tools/bim/commands/tx/shared/schedule/launchd.py`, `src/tools/bim/commands/tx/shared/schedule/cron.py`, `src/tools/bim/commands/tx/shared/schedule/installer.py`, `tests/tools/bim/tx/test_schedule.py`
### Module: Interfaces
- **Maps to capability**: Scheduled and shared execution
- **Location**: `src/tools/bim/tui/tx.py`, `tests/tools/bim/tx/test_interfaces.py`, `src/tools/bim/tx_cli.py`, `src/tools/bim/dependencies.py`, `src/tools/bim/commands/serve/_actions.py`, `src/tools/bim/tui/query.py`, `src/tools/bim/manifest.toml`, `src/tools/bim/SKILL.md`, `docs/source/tools/bim.rst`, `tests/tools/bim/test_serve_actions.py`, `tests/tools/bim/test_serve_security.py`, `CHANGELOG.md`
- **Responsibility**: Shared command composition, CLI/action/TUI adapters and operational documentation.
- **Exports**: Shared command composition, CLI/action/TUI adapters and operational documentation.
New symbols: `src/tools/bim/tui/tx.py`, `tests/tools/bim/tx/test_interfaces.py`

## Dependency Graph

### Foundation Layer (Phase 0)
- **Maintenance**: Depends on 00150 format and 00153 source provenance/transaction helpers; no scheduler/UI dependency.

### Core Layer (Phase 1)
- **Scheduler**: Depends on [Maintenance, 00153 Ingest pipeline, 00151 backend policy].

### Integration Layer (Phase 2)
- **Interfaces**: Depends on [Maintenance, Scheduler] and all earlier tx commands.

## Implementation Phases

### Phase 0: Foundation
**Goal**: Port the maintenance graph and rules.

**Tasks**:
- [ ] Implement lint, graph, lifecycle/assent transitions and MOC sync (depends on: 00153). Acceptance: `uv run pytest tests/tools/bim/tx/test_maintain.py` covers source rule parity, same-source exclusions, malformed notes/MOCs, fleeting→evergreen convergence, distinct commits and a second no-op run.

**Exit Criteria**: Rule fixtures retain behavior except the explicit within-run convergence requirement.

### Phase 1: Core
**Goal**: Protect prune and schedule operations.

**Tasks**:
- [ ] Add candidate reporting and opt-in pruning (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/bim/tx/test_prune.py` covers default-off, external backlinks, dirty files, delivered-as, own-source exclusion, target-only doubt cleanup and execution-time premise change skip/report.
- [ ] Port schedule install/status/uninstall (depends on: Phase 0 and 00153). Acceptance: `uv run pytest tests/tools/bim/tx/test_schedule.py` round-trips both platforms with exact label/marker, PATH, semicolon, logs, hash ownership and generic-backend refusal.

**Exit Criteria**: Scratch vault remains protected; mocked scheduler round trips preserve unowned artifacts.

### Phase 2: Integration
**Goal**: Expose common operations everywhere.

**Tasks**:
- [ ] Wire shared command classes into CLI, serve action registry and TUI; document commands/settings/skill and update manifest/changelog (depends on: Phase 1). Acceptance: `uv run pytest tests/tools/bim/tx/test_interfaces.py tests/tools/bim/test_serve_actions.py tests/tools/bim/test_serve_security.py` checks all four required operations, equivalent results, dry-run propagation and auth/path safeguards.
- [ ] Close all operational parity cases (depends on: interface wiring). Acceptance: `uv run pytest tests/tools/bim/tx/test_maintain.py tests/tools/bim/tx/test_schedule.py -k settings` individually overrides every tx threshold and git identity to assert matching behavior.

**Exit Criteria**: `uv run pytest`, `uv run mypy src/lib/ src/tools/` and `uv run sphinx-build -b html docs/source docs/build/html` pass once at closeout.

## Test Strategy

### Critical Scenarios
- **Happy path**: one maintain invocation completes eligible transitions; second creates no note/commit, but stamps last_maintain.
- **Edge case**: private note links to prune candidate; private bytes never change and candidate is protected.
- **Error case**: dirty MOC, malformed note, changed scheduler artifact and interrupted maintain preserve other agents' work and release locks.
- **Integration**: Textual headless tests and HTTP test client drive the same commands as CLI; no manual UI check.

## Risks

- **Source inconsistency**: old planner advances one lifecycle step per run; discovery's second-run no-op contract wins, so test the stronger fixture explicitly.
- **Boundary exception**: private backlink scanning is local/read-only and solely for prune protection; it is not permission to include private notes in LLM context.
- **Schedule effects**: installer tests use fake homes/subprocesses; implementation never installs jobs on the developer's host.
