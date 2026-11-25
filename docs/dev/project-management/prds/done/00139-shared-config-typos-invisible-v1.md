---
design: required
default_model: opus
model_tier_rationale: needs a library-level registry of every tool's keys without the library importing tool code
---

# Typos in shared config files are never reported

Source: agoge runs `docs/dev/project-management/audit-results/agoge-2026-11-10-2.md` (finding 13, LOW, lane heidi, deferred) and `agoge-2026-11-12.md` (re-observed by heidi).

## Overview

### Problem Statement

The unknown-key check exempts files by name: `config.yaml` and `buvis.yaml` may carry any key, because they hold settings for many tools. A typo there (`srouces:`) is silently ignored. The same file passed as `--config custom.yaml` is rejected, so one file passes or fails depending on its name.

### Target Users

Users who keep settings in the shared files.

### Success Metrics

- A top-level key in `config.yaml` / `buvis.yaml` that matches no tool's settings field, no global field, and no declared deferred key produces a warning naming the file and key.
- Valid shared keys for any tool produce no warning.

## Functional Decomposition

### Capability: Catch shared-file typos

#### Feature: Warn on keys no tool knows

- Warn (not fail) on shared-file keys that match no known key. Chosen option: agoge option (b).
- The library must not import tool code (AGENTS.md invariant): tools register their key sets, or the check runs from a place that already knows all tools. The design decides which.

## Structural Decomposition

- `src/lib/buvis/pybase/configuration/resolver.py` (`_load_yaml` file-name exemption)
- A key registry (location decided in design)
- `docs/source/configuration.rst`
- `CHANGELOG.md`

## Implementation Phases

### Phase 1: Design

- [ ] Choose how the library learns every tool's keys without importing tools.

### Phase 2: Core

- [ ] Warn on unknown shared keys - Acceptance: the evidence case warns; valid shared files stay quiet.
- [ ] CHANGELOG `Fixed` entry.

## Test Strategy

### Critical Scenarios

Evidence, verbatim:

```
`braid --config a/config.yaml` with `srouces:` -> rc 0
the same content as `custom.yaml` -> rc 2
```

## Risks

- A registry that misses a tool turns valid keys into noisy warnings.
- The warning surfaces as a bare log line until PRD 00140 lands.
