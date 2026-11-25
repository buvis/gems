---
design: skip
default_model: haiku
model_tier_rationale: one docs paragraph, search path given
---

# bim.rst does not state where saved queries are searched

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 12 of 13, LOW, lane wendy.

## Overview

### Problem Statement

`query_spec_parser.py` resolves saved queries through `get_config_dirs()`, so since PRD 00122 `~/.local/.config/buvis/queries/` is also searched. Templates are documented (`zettel.rst:136`), but `bim.rst` never states the query search path, so users will not find the feature. Stable.

### Target Users

bim users who keep saved queries.

### Success Metrics

- `bim.rst`, under `bim query`, lists every directory searched for saved queries, including `~/.local/.config/buvis/queries/`, in resolution order.

## Functional Decomposition

### Capability: Documented query search path

#### Feature: Add the path to `bim.rst`

- Chosen option: agoge option 1. Check the other `get_config_dirs()` consumers and note any with the same gap in the PR description.

## Structural Decomposition

- `docs/source/tools/bim.rst`

## Implementation Phases

### Phase 1: Core

- [ ] docs: add the query search path under `bim query` - Acceptance: the section lists the directories; `sphinx-build` passes.

## Test Strategy

### Critical Scenarios

Evidence from the run, verbatim (the behavior the docs must describe):

```
With `~/.local/.config/buvis/queries/wendy-local-only.yaml` present, `bim query -l` listed `wendy-local-only  .../.local/.config/buvis/queries/wendy-local-only.yaml`, rc=0.
```

## Risks

- None. The same gap may exist for other config-dir consumers; a single table in `configuration.rst` (agoge option 2) was not chosen.
