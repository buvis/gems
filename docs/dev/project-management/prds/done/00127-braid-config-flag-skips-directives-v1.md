---
design: skip
default_model: sonnet
model_tier_rationale: one resolver path routed through the existing merge helper; repro given verbatim
---

# --config FILE must apply list directives and env substitution like discovered config

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 5 of 13, MEDIUM, lane heidi.

## Overview

### Problem Statement

For an explicit `--config` file, `ConfigResolver._load_yaml` (`resolver.py`) does a raw `yaml.safe_load`: no directive merge and no `${VAR}` expansion. Keys such as `sources+`, `policies+`, `policies-` are dropped. sysup's plan path handles the same file correctly. It predates PRD 00123, which made it visible. A user who tests a config with `--config` sees different behavior than with the discovered file.

### Target Users

Anyone debugging config with `--config`, braid users most of all.

### Success Metrics

- `braid --config x.yaml --dry-run` with `policies+: [pol.braidignore]` prints `1 ignored`, the same as the local layer.
- `braid --config y.yaml` with only `sources+: [a]` links skill `a` instead of `no skill sources configured`.
- `${HOME}` in `--config` is expanded.

## Functional Decomposition

### Capability: One load path for explicit config

#### Feature: Route `--config` through `merge_configs`

- Load an explicit path via `loader.merge_configs(loader.load_yaml(path))`, the path sysup uses. Chosen option: agoge option 1.

## Structural Decomposition

- `src/lib/buvis/pybase/configuration/resolver.py` (`ConfigResolver._load_yaml`)
- `docs/source/configuration.rst`, `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] lib: route explicit config through the shared merge path - Acceptance: all three repro cases behave like the discovered file.
- [ ] CHANGELOG `Fixed` entry.

## Test Strategy

### Critical Scenarios

Regression test, failing against current code first. Evidence from the run, verbatim:

```
- `braid --config x.yaml --dry-run` with `policies+: [pol.braidignore]` printed `0 ignored`. The same file in the local layer gave `1 ignored`.
- `braid --config y.yaml` with only `sources+: [a]` printed `no skill sources configured`, rc=2.
- `sources: [${HOME}/../src/a]` via `--config` printed `sources entry must be absolute ...`.
- `sysup --config s.yaml --dry-run` expanded `${HOME}` correctly.
```

## Risks

- Shared-library change: a tool whose `--config` file holds literal `${...}` text would change behavior. Run every tool's tests.
