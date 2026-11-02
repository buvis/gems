---
catchup: skip
design: skip
ledger: deferred/202610292344-deferred.json
ledger_key: b23649226bd8
source_prd: 00109-backup-bundle-items-and-skip-outcomes-v1.md
severity: high
---

# Triage: A bundle whose out lies under source but under no selected item is rejected b...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610292344`, ledger `deferred/202610292344-deferred.json`, type `deferred_decision`, cycle `1`, raised against `00109-backup-bundle-items-and-skip-outcomes-v1.md`.

Issue: A bundle whose out lies under source but under no selected item is rejected by the unconditional containment check, blocking the PRD's headline case (source: ~, items .gitconfig/.npmrc, out under ~/.local/backup)

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `b23649226bd8`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `b23649226bd8` from `00109-backup-bundle-items-and-skip-outcomes-v1.md` until a human triages it
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
