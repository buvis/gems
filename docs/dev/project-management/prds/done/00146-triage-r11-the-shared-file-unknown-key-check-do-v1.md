---
catchup: skip
design: skip
ledger: deferred/202611131903-deferred.json
ledger_key: 2e8f3678cb9e
source_prd: 00139-shared-config-typos-invisible-v1.md
severity: high
---

# Triage: R11: the shared-file unknown-key check does not know other tools settings fie...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202611131903`, ledger `deferred/202611131903-deferred.json`, type `requirements-ambiguity`, consensus `1/4`, raised against `00139-shared-config-typos-invisible-v1.md`.

Issue: R11: the shared-file unknown-key check does not know other tools settings fields, so a top-level sources: (braid field) warns when sysup resolves config.yaml. PRD Success Metric 1 says any tools settings field; the approved design says shared files carry <tool>: namespace sections instead, and per-tool field sets would make the library import tool code against the AGENTS.md invariant.

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `2e8f3678cb9e`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `2e8f3678cb9e` from `00139-shared-config-typos-invisible-v1.md` until a human triages it
- **Exports**: none

### Dependencies
- triage: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [x] triage: promote to backlog or close - Acceptance: this file is no longer under docs/dev/project-management/prds/hold/

### Phase 1: Core
No implementation tasks until attended triage.

## Success Criteria

- This file is no longer under `docs/dev/project-management/prds/hold/`.

## Triage

Closed 2026-11-16 under the user’s accepted fourth agoge walk, finding 2. Shared tool sections are ignored with a warning directing values to buvis-<tool>.yaml. Implemented in `0d679585`; configuration regression tests verify the decision. No backlog work remains for this ledger key.
