---
catchup: skip
design: skip
ledger: deferred/202610121200-deferred.json
ledger_key: bb826767ff64
source_prd: 00099-dot-shared-config-host-fragments-v1.md
severity: 🟠
---

# Triage: The configured driver commands are 'dot filter clean -- %f' / 'smudge -- %f';...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610121200`, ledger `deferred/202610121200-deferred.json`, type `deferred_decision`, cycle `1`, op_id `f466807a42d7-dd0`, raised against `00099-dot-shared-config-host-fragments-v1.md`.

Issue: The configured driver commands are 'dot filter clean -- %f' / 'smudge -- %f'; the PRD pins the exact values without '--'. The '--' is the guard the PRD's own shell-unsafe-path requirement needs, so this is a requirements conflict a human must settle.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `bb826767ff64`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `bb826767ff64` from `00099-dot-shared-config-host-fragments-v1.md` until a human triages it
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

Closed 2026-10-25 as the cycle-1 twin of `00100-triage-filter-driver-config-values-are-buvis-au-v1.md`: same finding, same decision, the `--` guard in the driver commands stays.
