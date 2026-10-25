---
catchup: skip
design: skip
ledger: deferred/202610121200-deferred.json
ledger_key: 0db5aab31f55
source_prd: 00099-dot-shared-config-host-fragments-v1.md
severity: high
---

# Triage: Filter driver config values are "BUVIS_AUTO_UPDATE=false dot filter clean --...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610121200`, ledger `deferred/202610121200-deferred.json`, type `requirements-ambiguity`, cycle `1`, consensus `1/4`, raised against `00099-dot-shared-config-host-fragments-v1.md`.

Issue: Filter driver config values are "BUVIS_AUTO_UPDATE=false dot filter clean -- %f" / "... smudge -- %f"; PRD 00099 pins the exact values without "--". The "--" is the guard the PRD's own shell-unsafe-path requirement needs, so the PRD and the code conflict on a point a human must settle.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `0db5aab31f55`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `0db5aab31f55` from `00099-dot-shared-config-host-fragments-v1.md` until a human triages it
- **Exports**: none

### Dependencies
- triage: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] triage: promote to backlog or close - Acceptance: this file is no longer under docs/dev/project-management/prds/hold/

### Phase 1: Core
No implementation tasks until attended triage.

## Success Criteria

- This file is no longer under `docs/dev/project-management/prds/hold/`.

## Triage

Closed 2026-10-25, the code wins. `dot filter clean -- %f` needs `--` so a leading-dash path is never read as an option, which is the PRD's own shell-unsafe-path requirement; the PRD text that pins the values without `--` was the stale side. `FILTER_CLEAN_VALUE` and `FILTER_SMUDGE_VALUE` in `src/tools/dot/git/filter_driver.py` stay as they are, and `test_share_succeeds_for_a_tracked_leading_dash_name` in `tests/tools/dot/test_shared_real_git.py` pins the behavior. The decision is recorded in PRD 00099's triage section.
