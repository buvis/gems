---
design: skip
default_model: sonnet
model_tier_rationale: one narrow except clause in braid's engine; repro given verbatim
---

# Malformed braid `sources` entries must fail with a message, not a traceback

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 7 of 13, LOW, lane trudy.

## Overview

### Problem Statement

`_expand_configured` in braid's `engine.py` (new in PRD 00123) lets `RuntimeError` and `ValueError` escape, and compose catches only `BraidError` and `OSError`. A rare typo in `sources` gives a traceback instead of a message. Finding 2 of the same run (PRD 00125) covers the wider class.

### Target Users

braid users with a mistyped `~user/...` entry or a path with an embedded NUL.

### Success Metrics

- Both repro entries exit with rc=2 and one console message naming the entry, with no traceback.

## Functional Decomposition

### Capability: Clean source-expansion errors

#### Feature: Re-raise as `BraidError`

- Catch `RuntimeError` and `ValueError` in `_expand_configured` and re-raise as `BraidError`. Chosen option: agoge option 1.

## Structural Decomposition

- `src/tools/braid/engine.py` (`_expand_configured`)
- `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] braid: convert expansion errors to `BraidError` - Acceptance: both repro entries exit 2 without a traceback.
- [ ] CHANGELOG `Fixed` entry.

## Test Strategy

### Critical Scenarios

Regression test, failing against current code first. Evidence from the run, verbatim:

```
- `sources: [~nosuchuser_agoge/x]` gave a traceback ending `RuntimeError: Could not determine home directory.`, rc=1.
- An embedded NUL gave `ValueError: lstat: embedded null character in path`.
- `~root/x`, `~/../../etc`, a symlink loop, a file and a 5000-char path all failed cleanly with rc=2.
```

## Risks

- None of substance: a narrow patch.
