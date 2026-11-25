---
catchup: skip
design: skip
ledger: deferred/202611131903-deferred.json
ledger_key: bb78424024a2
source_prd: 00137-yaml-auto-update-ignored-v1.md
severity: critical
---

# Triage: R4 CRITICAL: the new _run_update_check_once(ctx, args) signature breaks tests...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202611131903`, ledger `deferred/202611131903-deferred.json`, type `review-finding`, cycle `1`, consensus `1/4`, raised against `00137-yaml-auto-update-ignored-v1.md`.

Issue: R4 CRITICAL: the new _run_update_check_once(ctx, args) signature breaks tests/tools/sysup/conftest.py:20 (lambda _ctx: None), producing 86 failed / 10 errors across tests/tools/sysup and tests/tools/dot (76 TypeError occurrences) at head 28a0580d

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `bb78424024a2`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `bb78424024a2` from `00137-yaml-auto-update-ignored-v1.md` until a human triages it
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
