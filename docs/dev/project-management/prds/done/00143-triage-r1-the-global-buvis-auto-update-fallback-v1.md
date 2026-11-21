---
catchup: skip
design: skip
ledger: deferred/202611131903-deferred.json
ledger_key: 2faaf51c2c4e
source_prd: 00137-yaml-auto-update-ignored-v1.md
severity: high
---

# Triage: R1: the global BUVIS_AUTO_UPDATE fallback changes the `enabled` decision with...

## Problem

Deferred finding with no PRD owner when this stub was minted: batch `202611131903`, ledger `deferred/202611131903-deferred.json`, type `cap-overflow`, cycle `2`, consensus `1/4`, op_id `56960689a254-dd0`, raised against `00137-yaml-auto-update-ignored-v1.md`.

Issue: R1: the global BUVIS_AUTO_UPDATE fallback changes the `enabled` decision without changing the settings object passed to the updater, so with a tool-prefixed settings class, BUVIS_AUTO_UPDATE=true and YAML auto_update: false the updater receives settings.auto_update=False and returns immediately. test_global_env_true_runs_tool_check_despite_yaml_false only counts mocked calls, so it pins behaviour production never has. Introduced by the cycle-1 rework (commit a55906ab, src/lib/buvis/pybase/configuration/click_integration.py:210).

## Solution

Attended triage. A human promotes this finding into a backlog PRD through normal PRD authoring and review, or closes it. Autopilot never drains `docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `2faaf51c2c4e`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
- **Responsibility**: hold ledger key `2faaf51c2c4e` from `00137-yaml-auto-update-ignored-v1.md` until a human triages it
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

Closed 2026-11-16 under the user’s accepted fourth agoge walk, finding 5. Environment values, including defaults, beat YAML; the updater receives the effective auto_update value. Implemented in `0d679585`; configuration regression tests verify the decision. No backlog work remains for this ledger key.
