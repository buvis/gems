---
catchup: skip
design: skip
ledger: deferred/202611250933-deferred.json
ledger_key: ab652f9e458e
source_prd: 00177-update-fails-on-stale-uv-index-v1.md
severity: high
---

# Triage: Pre-existing, outside the 00177 diff. Proposed fix: autouse BUVIS_DEV_MODE=1...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202611250933`, ledger `deferred/202611250933-deferred.json`, type `out-of-scope`, raised against `00177-update-fails-on-stale-uv-index-v1.md`.

Detail: Pre-existing, outside the 00177 diff. Proposed fix: autouse BUVIS_DEV_MODE=1 in tests/conftest.py, with the updater guard tests opting out. Found by eve delta review.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `ab652f9e458e`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `ab652f9e458e` from `00177-update-fails-on-stale-uv-index-v1.md` until a human triages it
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
