---
design: skip
default_model: haiku
model_tier_rationale: one-line docs fix, line cited
---

# Configuration docs say "first found wins" but the layers merge

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 11 of 13, LOW, lane wendy.

## Overview

### Problem Statement

`docs/source/configuration.rst:316` says "Config files are discovered in order (first found wins)", directly above the list PRD 00122 edited. The layers actually merge per key, so readers expect the wrong behavior. Stable.

### Target Users

Anyone reading the configuration docs to write a local config.

### Success Metrics

- The sentence says the files are merged in order and later layers win per key, and links the list-directive section.

## Functional Decomposition

### Capability: Correct docs sentence

#### Feature: One-line fix

- Replace the sentence. Chosen option: agoge option 1.

## Structural Decomposition

- `docs/source/configuration.rst`

## Implementation Phases

### Phase 1: Core

- [ ] docs: fix the sentence at `configuration.rst:316` - Acceptance: the sentence no longer says "first found wins"; `sphinx-build` passes.

## Test Strategy

### Critical Scenarios

Evidence from the run, verbatim (the behavior the sentence must describe):

```
A shared `sources: [skills-a]` plus a local `sources+: [skills-b]` linked alpha, beta and gamma. For sysup, shared and local entries merged by key.
```

## Risks

- None. Docs only, no CHANGELOG entry needed.
