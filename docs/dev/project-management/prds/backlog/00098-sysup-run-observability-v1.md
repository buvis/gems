---
default_model: opus
model_tier_rationale: subprocess result contracts and interrupt-safe log/refresher lifecycle require design and behavioral equivalence
---

# sysup run observability

Source: docs/dev/project-management/intake/processed/00098-sysup-run-observability/discovery.md

## Overview

### Problem Statement
Captured updates look hung, the sudo prompt lacks context, and exit-0 error output disappears. The attention layer reports outcomes but retains no complete run output.

### Target Users
The operator running sysup interactively or unattended who needs visible activity, immediate post-step diagnostics and retained evidence.

### Success Metrics
- Task-specific tests below cover discovery R1–R8 without real updates, sudo, network calls or wall-clock waits.
- Existing attention, expiry, notification, interactive execution and exit-code contracts remain covered; update result-count expectations for the selected one-final-result behavior.
- No new dependencies or library changes; Python 3.11 remains supported.

## Functional Decomposition

### Capability: Live execution
Make captured updates visibly active and surface errors as soon as capture completes.

#### Feature: Progress and diagnostics
- **Description**: Add transient progress to captured steps and capability iteration; retain capture rather than streaming.
- **Inputs**: Selected entries, argv, interactive flag, captured stdout/stderr and return code.
- **Outputs**: Status text `<entry>: <argv joined>` or `<entry>: <use>`, immediate failure diagnostics, condensed exit-0 error lines and entry outcomes.
- **Behavior**: Use the existing console status context around each captured spawn and the complete capability iteration; never wrap interactive steps. After each successful captured step, scan stdout then stderr lines with case-insensitive `^\s*error:`. Print at most five matches per step followed by `+N more, see log` for omitted matches, before the next step starts. Count all matches across the entry. Every steps-based entry yields exactly one final `StepResult`, including with continue-on-error: failed if any step failed or timed out, otherwise warned if any matches occurred, otherwise ok. A warned result has success true, command set to the entry and message `<entry>: N error line(s), see log`. Show failures immediately as diagnostics and retain every failure detail in the final failed result; diagnostics are not additional persisted results. Abort on the first failure unless continue-on-error is true. Emit no intermediate success lines and do not buffer success lines for later display. Keep capability result behavior and raw-output capture/classification unchanged. Non-TTY status renders no escape sequences.

#### Feature: Timeout outcomes
- **Description**: Turn subprocess timeouts into failed results and retain partial output.
- **Inputs**: Configured timeout and timeout exception, including optional byte or text stdout/stderr.
- **Outputs**: Failed result with message `<entry> timed out after Ns` and available partial output in the run log.
- **Behavior**: Catch subprocess timeouts in captured and interactive argv branches. Preserve ordinary nonzero-exit stderr reporting; no traceback. Keep sudo stop callbacks and log cleanup in finally, including interrupt exits.

### Capability: Conditional sudo preparation
Frame only the credential prompt needed by the selected plan.

#### Feature: Selected-plan sudo prime
- **Description**: Add an opt-in sudo flag and skip unnecessary or unattended priming.
- **Inputs**: Configured prime capabilities, selected plan and stdin TTY state.
- **Outputs**: Optional contextual banner, branded prompt and existing refresher stop callback.
- **Behavior**: Add `sudo: bool = False` to `SysupCommand`, retain forbidden unknown keys and set brew's flag true. Invoke configured sudo-prime only when stdin is a TTY and any selected entry has sudo true or any step's first token equals sudo. Preserve `prime: []`. In `SudoPrime.prime`, after sudo resolves on PATH and immediately before spawning sudo -v, emit one console info line explaining credential caching for cask upgrades, Ctrl-D to skip and later steps prompting themselves. Use argv `[sudo_path, "-p", "sysup needs your password: ", "-v"]`. Never claim Ctrl-C skips. Missing sudo or declined prime remains nonfatal and starts no refresher; preserve refresher cleanup.

### Capability: Retained run evidence
Keep complete captured output and integrate amber findings with existing attention handling.

#### Feature: Per-run log lifecycle
- **Description**: Write an append-per-step log for every ordinary run, including empty plans.
- **Inputs**: UTC start time, selected plan names, executed steps, outcomes and complete captured stdout/stderr.
- **Outputs**: Log under `$XDG_STATE_HOME/sysup/logs/`, falling back to `~/.local/state/sysup/logs/`, and one final console line `full log: <path>`.
- **Behavior**: Header records UTC start and plan names. Base filename uses UTC `%Y%m%dT%H%M%SZ.log`. At run start keep the newest nine prior run files, then create this run's file; append and flush each completed step. Captured sections start `=== <entry>: <argv> (exit N) ===` and preserve both streams. Interactive steps and each capability result have `=== <entry>: <use or argv> (<status>, not captured) ===` markers. Timeout sections identify the timeout rather than inventing an exit code and retain available partial output. Close on every exit. List, dry-run, status and refresh create no log. For completed runs, print the path after the ordinary attention summary even for clean runs. This append-only evidence file is not a note, state file or config; attention persistence continues using its existing atomic writer.
- **Behavior**: Create logs exclusively; on a same-second collision append the first available positive integer suffix before the extension: `20261018T120000Z.log`, `20261018T120000Z-1.log`, `20261018T120000Z-2.log`. Retry exclusive creation on collisions; never overwrite. Retention orders by file modification time with filename as tie-breaker. Premise: only regular files matching the generated timestamp/suffix log naming scheme are disposable run logs. Re-check that premise before each deletion; skip and report mismatches, never delete unrelated files. On log creation, pruning, append, flush or close failure, raise the existing `FatalError` through the runner to the CLI's controlled error handler: no traceback and exit 1. Creation/pruning failure starts no update steps; a later write failure starts no further update steps, even with continue-on-error. Preserve already flushed evidence and completed updates; release log and sudo resources in finally. Follow the existing fatal-run behavior: do not fold partial results into attention state or send a completed-run notification. Omit the completed-run `full log:` line on failure; identify any retained path as incomplete in the error diagnostic. Never roll back updates or treat an incomplete log as complete.

#### Feature: Amber attention outcome
- **Description**: Extend the attention schema and renderer with warned status.
- **Inputs**: Warned result, prior attention state, checked names and notification configuration.
- **Outputs**: One amber summary entry, version-one state, notification under existing rules and exit 0 unless a red result exists.
- **Behavior**: Add warned to `Status`; place it below expiring in `_RANK`, admitting it through `_valid_entry`. Leave `RED` unchanged. Render warned via console warning. Preserve folding, notification deduplication and ntfy body construction using the first stored detail; the warned count message becomes that detail. A clean recheck clears warned; unchecked entries persist.

Scope excludes streaming/tee, raw capability output retention, interactive behavior changes beyond timeout handling, external ntfy hook changes, spinner step indices and newest-log display in status. Non-TTY guarantees cover sysup's progress and sudo prime only; child commands retain their input behavior and may prompt. Discovery open questions resolve to its strict regex, existing ntfy rule, banner inside prime and UTC filename default. Internal capture-record shapes and log API signatures belong to the design phase; no human decisions remain for implementation.

## Structural Decomposition

### Repository Structure

```text
src/tools/sysup/
├── config.py                       # sudo configuration
├── default.yaml                    # brew sudo flag
├── step_result.py                  # warned status
├── attention.py                    # warned persistence/ranking
├── runlog.py                       # new run evidence
├── runner.py                       # progress, capture, timeouts, logging
├── capabilities/
│   └── sudo.py                     # contextual branded prime
└── cli.py                          # warning renderer and final log path
tests/tools/sysup/
├── test_config.py
├── test_default_config.py
├── test_step_result.py
├── test_attention.py
├── test_runlog.py                   # new log tests
├── test_runner.py
├── test_sudo.py
├── test_sysup_cli.py
└── test_invariants.py
docs/source/tools/sysup.rst
CHANGELOG.md
```

### Module: Configuration and preparation
- **Maps to capability**: Conditional sudo preparation
- **Location**: src/tools/sysup/config.py, src/tools/sysup/default.yaml, src/tools/sysup/capabilities/sudo.py
- **Responsibility**: Validate additive config and frame the optional credential prime.
- **Exports**: Existing `SysupCommand`, `SudoPrime`; preserve capability registration.

### Module: Run evidence
- **Maps to capability**: Retained run evidence
- **Location**: src/tools/sysup/runlog.py
- **Responsibility**: Resolve directory, prune old run files, create header, append/flush complete sections and close resources.
- **Exports**: `logs_dir`, `open_run_log`, `append_step`, `prune`.
- New symbols: `src/tools/sysup/runlog.py`, `logs_dir`, `open_run_log`, `append_step`, `prune`, `tests/tools/sysup/test_runlog.py`.

### Module: Execution
- **Maps to capability**: Live execution; Conditional sudo preparation; Retained run evidence
- **Location**: src/tools/sysup/runner.py
- **Responsibility**: Integrate progress, retained capture, conditional prime, classification and log ownership in shared execution. Own every console status context and print the mid-entry diagnostics (immediate failure details, the condensed exit-0 error lines and their overflow line) through the console adapter from src/tools/sysup/runner.py, before the next step starts; the CLI never prints them.
- **Exports**: Existing `Runner` and yielded `StepResult`; expose the written log path to CLI without duplicating logic.

### Module: Attention and presentation
- **Maps to capability**: Retained run evidence; Live execution
- **Location**: src/tools/sysup/step_result.py, src/tools/sysup/attention.py, src/tools/sysup/cli.py
- **Responsibility**: Admit warned as lowest amber severity; render yielded outcomes and the final log path through the console adapter (mid-entry diagnostics are printed by Execution, not here).
- **Exports**: Existing `Status`, `StepResult`, `fold_results`, `exit_code`, CLI and status command.

### Module: Verification and documentation
- **Maps to capability**: Live execution; Conditional sudo preparation; Retained run evidence
- **Responsibility**: Headless regression coverage in listed tests, user documentation and unreleased sysup changelog entries.
- **Exports**: Pytest scenarios and documented behavior; no runtime API.

## Dependency Graph

### Foundation Layer (Phase 0)
- **Configuration and preparation**: No dependencies; config and contextual prime.
- **Run evidence**: No new-module dependencies; follows existing attention XDG resolution.
- **Attention and presentation (status support)**: No new-module dependencies; status, rank and warning renderer.

### Core Layer (Phase 1)
- **Execution**: Depends on [Configuration and preparation, Run evidence, Attention and presentation (status support)].

### Integration Layer (Phase 2)
- **Attention and presentation (CLI integration)**: Depends on [Execution, Run evidence].
- **Verification and documentation**: Depends on [Execution, Attention and presentation (CLI integration)].

## Implementation Phases

### Phase 0: Foundation
**Goal**: Establish config, amber status and log primitives.

**Tasks**:
- [ ] Add sudo flag/default and contextual prime in src/tools/sysup/config.py, src/tools/sysup/default.yaml and src/tools/sysup/capabilities/sudo.py; extend tests/tools/sysup/test_config.py, tests/tools/sysup/test_default_config.py and tests/tools/sysup/test_sudo.py (no deps). Acceptance: `uv run pytest tests/tools/sysup/test_config.py tests/tools/sysup/test_default_config.py tests/tools/sysup/test_sudo.py -q` covers false default, brew true, legacy config, banner-before-branded-argv ordering, decline and missing sudo.
- [ ] Extend src/tools/sysup/step_result.py, src/tools/sysup/attention.py and warning dispatch in src/tools/sysup/cli.py; add tests/tools/sysup/test_step_result.py and tests/tools/sysup/test_attention.py coverage (no deps). Acceptance: `uv run pytest tests/tools/sysup/test_step_result.py tests/tools/sysup/test_attention.py -q` covers warned roundtrip, rank below expiring, notify once, clean clearance, unchecked retention and exit 0.
- [ ] Implement src/tools/sysup/runlog.py and tests/tools/sysup/test_runlog.py (no deps). Acceptance: `uv run pytest tests/tools/sysup/test_runlog.py -q` covers XDG/fallback, header, both complete streams, markers, timeout bytes/text, flush, 11 sequential runs retaining 10, same-second collisions, execution-time regular-file/name premise checks before pruning (skip and report mismatches), close-on-error, controlled fatal I/O failures and preservation of flushed evidence.

**Exit Criteria**: Foundation task tests pass without real subprocesses or notifications.

### Phase 1: Core
**Goal**: Integrate progress, logs, conditional priming and timeouts.

**Tasks**:
- [ ] Update src/tools/sysup/runner.py and tests/tools/sysup/test_runner.py for status contexts, selected-plan prime, logs and timeouts (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/sysup/test_runner.py -q` covers captured status text, whole multi-result capability iteration, no interactive spinner, TTY/flag/argv sudo predicates, dry-run isolation, cleanup on interrupt and fatal log errors, output/timeout retention, zero update spawns after creation/pruning failure and no further update spawns after append/flush failure, including continue-on-error and multi-result capabilities. Adapt existing prime fixtures to select sudo-needing commands and mock TTY; retain ordering/cleanup assertions. Premise: tests/tools/sysup/test_runner.py holds four prime tests that build MagicMock(spec=SudoPrime) (rg -c -F "MagicMock(spec=SudoPrime)" tests/tools/sysup/test_runner.py prints 4); re-check before editing, adapt all four, delete none.
- [ ] Integrate exit-0 extraction and one final result per steps-based entry in src/tools/sysup/runner.py and src/tools/sysup/cli.py; add observability-named cases in tests/tools/sysup/test_runner.py and tests/tools/sysup/test_sysup_cli.py (depends on: preceding task). Acceptance: `uv run pytest tests/tools/sysup/test_runner.py tests/tools/sysup/test_sysup_cli.py -k observability -q` covers case/whitespace matching, excluded mise prefix and Warning lines, stream ordering, seven matches printing five plus overflow, middle-step diagnostics before next spawn, clean last-step preservation of warning, exactly one final result for clean/warned/failed continue-on-error entries, immediate failure diagnostics, all failure details retained, no intermediate success lines and red dominance. Update existing per-step result-count assertions while preserving abort/continue execution coverage.

**Exit Criteria**: Observability tests pass with mocked subprocesses and ordered console-call assertions.

### Phase 2: Integration
**Goal**: Complete ordinary CLI lifecycle and documentation.

**Tasks**:
- [ ] Finish log-path and warned integration in src/tools/sysup/cli.py; extend tests/tools/sysup/test_sysup_cli.py and include the log module in tests/tools/sysup/test_invariants.py (depends on: Phase 1). Acceptance: `uv run pytest tests/tools/sysup/test_sysup_cli.py tests/tools/sysup/test_invariants.py -q` covers warned rendering/state/notify-once/exit-0/clean-clear, ntfy count detail, red exits, one final path line on clean/amber runs, no logs for inspection/dry-run/refresh, and controlled log errors exiting 1 without traceback, attention-state changes, notifications or a completed-log claim; any retained path is explicitly incomplete. Include a real nonterminal Rich console test: no escapes, ordinary result lines retained.
- [ ] Document sudo (include a YAML example line sudo: true), prime conditions, Ctrl-D versus Ctrl-C, child-input scope, strict heuristic, warned semantics, one final result per steps-based entry, log format/path/retention (describe retention as keeping the newest 10 files), collision suffixes, stop-on-log-failure behavior and capability-output limits in docs/source/tools/sysup.rst; add Added and Changed sysup entries to CHANGELOG.md (depends on: CLI integration). Acceptance: `uv run sphinx-build -b html docs/source docs/build/html` succeeds; `python3 -c 'from pathlib import Path; d=Path("docs/source/tools/sysup.rst").read_text(); assert all(s in d for s in ("sudo:", "warned", "Ctrl-D", "Ctrl-C", "logs/", "newest 10", "error:")); c=Path("CHANGELOG.md").read_text().split("## [", 2)[1]; assert "**sysup**:" in c and "### Added" in c and "### Changed" in c'` passes after documenting every contract above.

**Exit Criteria**: `uv run pytest -m sysup -q`, `uv run mypy src/tools/sysup`, `uv run ruff check src/tools/sysup tests/tools/sysup` and the final project suite `uv run pytest` pass after all tasks; run the full suite only once here.

## Test Strategy

### Critical Scenarios
- **Happy path**: Captured brew steps show status and retain complete output; branded prime runs only for an eligible TTY plan.
- **Edge case**: Middle-step exit-0 errors surface before next spawn; one warned result persists, notifies once, exits 0 and clears on clean recheck.
- **Edge case**: Same-second runs never overwrite; retention removes only older run logs.
- **Error case**: Nonzero exits remain red; timeout partial output survives. Log creation/pruning failure starts no updates; append/flush failure preserves earlier evidence and stops further updates. Controlled errors exit 1, leave prior attention state unchanged, send no completed-run notification and identify partial logs as incomplete. Interrupt closes resources and stops sudo refresh.
- Mock subprocesses, time and threading; use temporary XDG directories and a real nonterminal console. Never execute maintenance commands in tests.

## Risks

- **Prompt after declined prime**: Document sudo true for custom entries; preserve later child prompting.
- **Heuristic misses/noise**: Strict error-prefix matching creates amber only; complete logs support future refinement.
- **Log volume**: Ten files, no size cap; document location and full-output retention.
- **Older state readers**: Older builds reject warned entries; retain version one as accepted in discovery.
- **Rendering order**: Assert capability iteration and diagnostic order; pin real nonterminal rendering.
