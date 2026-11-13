---
design: skip
default_model: sonnet
model_tier_rationale: one warning in resolve_settings; repro given verbatim
---

# A configured braid `policies` entry that is not a file must warn

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 8 of 13, LOW, lane trudy.

## Overview

### Problem Statement

`resolve_settings` in braid's `engine.py` keeps only paths where `is_file()` is true, so a configured `policies` entry that is missing, a directory or a device is dropped with no message. The docs say "every file that exists", so the skip is by design, but a mistyped deny-list path silently stops hiding skills. Low likelihood, stable.

### Target Users

braid users who hide skills through `policies`.

### Success Metrics

- Each of the four repro entries prints a warning naming the entry and why it was skipped; braid still exits 0 and still links.

## Functional Decomposition

### Capability: Policy entry warning

#### Feature: Warn, do not fail

- For an explicitly configured `policies` entry that is not a regular file, warn through the console and keep going, so optional entries keep working. Chosen option: agoge option 2.
- Update braid.rst to say a skipped entry warns.

## Structural Decomposition

- `src/tools/braid/engine.py` (`resolve_settings`)
- `docs/source/tools/braid.rst`, `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] braid: warn on a non-file `policies` entry - Acceptance: the four repro entries warn, FIFO and `/dev/zero` still do not hang.
- [ ] Docs and CHANGELOG `Changed` entry.

## Test Strategy

### Critical Scenarios

Regression test, failing against current code first. Evidence from the run, verbatim:

```
`policies: [<S>/p2/nope]`, a directory, a FIFO and `/dev/zero` each gave `WOULD LINK ...` and rc=0, with no warning. FIFO and `/dev/zero` did not hang.
```

## Risks

- A deny list that only warns still fails open if the warning goes unread; raising `BraidError` (agoge option 1) was the stricter choice, not taken.
