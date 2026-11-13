---
design: skip
default_model: sonnet
model_tier_rationale: shared console helper plus per-tool call sites; needs a survey of report_result callers
---

# Failed commands exit 0, so scripts cannot tell they failed

Source: agoge runs `docs/dev/project-management/audit-results/agoge-2026-11-10-2.md` (finding 10, MEDIUM, lane walter, deferred) and `agoge-2026-11-12.md` (re-observed by walter; `muc tidy` partial failure is the same class). Pre-existing.

## Overview

### Problem Statement

`console.report_result` prints ` ✘ <error>` for a failed `CommandResult` but does not change the exit status. `dot status` and `postup brief` therefore exit 0 on failure, and hooks, cron jobs and scripts treat the failure as success. `dot status` also runs `cfg secret hide -m`, a write, from a command that reads as read-only.

### Target Users

Anyone running buvis tools from scripts, hooks, or CI.

### Success Metrics

- `dot status` and `postup brief` exit non-zero when their `CommandResult` fails.
- No tool's CLI exits 0 after printing a ` ✘` failure from `report_result`.

## Functional Decomposition

### Capability: Exit status follows the result

#### Feature: Shared exit helper

- Give the console adapter (or the CLI layer) one way to exit non-zero on a failed `CommandResult` and use it in every tool's CLI. Chosen option: agoge option (b), the shared helper; option (a), fixing dot and postup only, is the fallback if (b) widens too far.
- Decide, and document in `dot.rst`, whether `dot status` should keep hiding secrets.

## Structural Decomposition

- `src/lib/buvis/pybase/adapters/console/console.py` (`report_result`)
- `src/tools/dot/cli.py`, `src/tools/dot/commands/status/status.py`
- `src/tools/postup/adapters/cli.py`, `src/tools/postup/commands/brief/brief.py`
- Every other `report_result` caller under `src/tools/` (survey)
- `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] Shared exit-on-failure path - Acceptance: the evidence commands exit non-zero.
- [ ] Survey and convert other `report_result` callers; list any deliberate exit-0 cases.
- [ ] CHANGELOG `Fixed` entry (exit status change, may affect scripts).

## Test Strategy

### Critical Scenarios

CliRunner tests per tool asserting the exit code on a failed result. Evidence, verbatim:

```
`DOTFILES_ROOT=<empty> dot status` -> ` ✘ Error hiding secrets: ...`, rc 0
`postup brief` with no data -> ` ✘ no data.json ...`, rc 0
```

## Risks

- Scripts that relied on exit 0 after a printed failure will start failing; call it out in the CHANGELOG.
- Wider blast radius across tools than fixing two CLIs.
