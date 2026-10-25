---
catchup: skip
design: skip
ledger: deferred/202610121200-deferred.json
ledger_key: 2fa1c8800566
source_prd: 00099-dot-shared-config-host-fragments-v1.md
severity: high
---

# Triage: Stage-failure path leaves a tokenized blob in the index without its attribute...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610121200`, ledger `deferred/202610121200-deferred.json`, type `cap-overflow`, cycle `2`, consensus `2/4`, op_id `f466807a42d7-dd2`, raised against `00099-dot-shared-config-host-fragments-v1.md`.

Issue: Stage-failure path leaves a tokenized blob in the index without its attribute registration staged, so an index-only commit can publish literal @HOME@ without a filter. The PRD clause and the design doc disagree here; cycle 1 chose the PRD wording and cycle 2's rework introduced the exposure (regression commit d19066d1).

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `2fa1c8800566`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `2fa1c8800566` from `00099-dot-shared-config-host-fragments-v1.md` until a human triages it
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

Closed 2026-10-25, fixed on master by `fix(dot): stage the attribute before renormalizing a shared file`.

The PRD clause (keep the registration, warn) and the design (full rollback) disagreed on what a failed `.gitattributes` stage leaves behind. Neither was taken. `CommandShare` now stages `.gitattributes` before it renormalizes the target, so a stage failure happens before any index change (attribute text restored, failure returned) and a renormalize failure restores the attribute file and its index entry through `restore_index_entry`. The tokenized-blob-without-attribute state is unreachable; the inverse half-state, reachable only when that index restore itself fails, is what every host already had before the share, and the error then names `dot unstage .gitattributes`. Regression tests: `TestCommandShareStageFailureLeavesIndexUntouched` and the three `test_renormalize_failure_*` tests in `tests/tools/dot/test_share.py`; the order is pinned by `test_writes_attribute_before_check_then_stages_then_renormalizes`.
