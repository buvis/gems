---
catchup: skip
design: skip
ledger: deferred/202610242315-deferred.json
ledger_key: 59e94f9ea936
source_prd: 00105-sysup-uv-tool-python-pin-v1.md
severity: high
---

# Triage: `engram` gets skipped with `success=False` on every run and stays unpinned. T...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202610242315`, ledger `deferred/202610242315-deferred.json`, type `deferred_decision`, cycle `1`, raised against `00105-sysup-uv-tool-python-pin-v1.md`.

Issue: `engram` gets skipped with `success=False` on every run and stays unpinned. The PRD names it as one of two motivating tools with compiled deps. Its real receipt is an editable install, and the requirement allowlist rejects it. A failed step is red, so `exit_code` returns 1 and `sysup` exits 1 on every run on this host. The skip itself is the right call; the real gap is the reinstall mechanism. `uv tool upgrade --python <target> <tool>` exists in the host uv and keeps the receipt's requirements; it is the likely fix

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `59e94f9ea936`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `59e94f9ea936` from `00105-sysup-uv-tool-python-pin-v1.md` until a human triages it
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
