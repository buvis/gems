---
catchup: skip
design: skip
ledger: deferred/202610292344-deferred.json
ledger_key: d1128c816565
source_prd: 00110-backup-plan-preview-and-output-resolution-v1.md
severity: high
---

# Triage: 30 of the new parametrized cases fail on Python 3.14, and CI's `tools` matrix...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610292344`, ledger `deferred/202610292344-deferred.json`, type `cap-overflow`, cycle `2`, consensus `2/6`, op_id `fb497c1e9deb-dd4`, raised against `00110-backup-plan-preview-and-output-resolution-v1.md`.

Issue: 30 of the new parametrized cases fail on Python 3.14, and CI's `tools` matrix runs 3.14 on both ubuntu and macOS. `_fail_metadata` injects errors by patching `Path.stat`. On 3.14, `Path.exists()` and `Path.is_dir()` call `os.path.exists`/`os.path.isdir` and never reach `Path.stat`, so the patched error never fires in `plan`. Reproduced with `uv run --python 3.14 pytest tests/tools/backup`: 30 failed, 485 passed. The failures are all of `test_runner_isolates_metadata_failures_and_preserves_independent_instances` and all of `test_runner_propagates_the_original_fatal_metadata_error`. The same command on 3.11 passes 515/515, and the gate ran only 3.13. Fix: inject the error through a seam that works on every version, for example wrap `TarArchive.plan` to raise for the blocked labels, since the runner's per-instance isolation is what these tests check.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `d1128c816565`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `d1128c816565` from `00110-backup-plan-preview-and-output-resolution-v1.md` until a human triages it
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
