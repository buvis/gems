---
design: skip
default_model: haiku
model_tier_rationale: one escape call in sysup's list renderer; cause must be confirmed first
---

# sysup --list drops the [run] / [use:x] kind label

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 13 of 13, LOW, lane heidi (out of lane). Predates PRDs 00122/00123.

## Overview

### Problem Statement

`sysup --list` prints each row with no kind label, so users cannot see how a step runs. The symptom was confirmed; the cause is suspected, not confirmed: Rich markup in `_describe` (`src/tools/sysup/cli.py`) swallows the bracketed label. Cosmetic, stable.

### Target Users

sysup users reading `sysup --list`.

### Success Metrics

- `sysup --list --only heidi_probe`-style output shows the label (`[run]` or `[use:x]`) on every row.

## Functional Decomposition

### Capability: Visible kind label

#### Feature: Escape the label

- First confirm the cause. If Rich is the cause, apply `rich.markup.escape` to the label. Chosen option: agoge option 1. If Rich is not the cause, fix where the label is lost and say so in the PR.

## Structural Decomposition

- `src/tools/sysup/cli.py` (`_describe`)
- `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] sysup: confirm why the label vanishes, then fix - Acceptance: every `--list` row shows its label.
- [ ] CHANGELOG `Fixed` entry.

## Test Strategy

### Critical Scenarios

Regression test, failing against current code first. Evidence from the run, verbatim:

```
`sysup --list --only heidi_probe` printed `   4  heidi_probe  `.
```

## Risks

- The suspected cause may be wrong; the fix may land elsewhere. Printing the list with markup off (agoge option 2) was not chosen because it loses other styling.
