---
design: skip
default_model: sonnet
model_tier_rationale: one warning path in the resolver; repro given verbatim
---

# Unknown keys in a tool's config must warn instead of being dropped silently

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 6 of 13, LOW, lanes walter, heidi.

## Overview

### Problem Statement

`BraidSettings` declares `extra="forbid"`, but `_merge_overrides` in `resolver.py` drops YAML keys that are not model fields before validation. A typo such as `srouces:` or a removed key such as `config_root:` silently does nothing. A user's typo is likely at a low rate and stable.

### Target Users

Anyone hand-writing `buvis-<tool>.yaml`, braid users first.

### Success Metrics

- `sources: [a]` plus `sorces+: [b]` prints a warning naming `sorces+`.
- `config_root: /x` and `srouces:` print the same kind of warning.
- Keys that are valid fields, and directive forms of them (`sources+`), do not warn.

## Functional Decomposition

### Capability: Unknown-key warning

#### Feature: Pass known keys to the merge

- Pass `known_keys=set(settings_class.model_fields)` from the resolver to `merge_configs` and warn on unknown keys. Chosen option: agoge option 1 (all tools).

## Structural Decomposition

- `src/lib/buvis/pybase/configuration/resolver.py` (`_merge_overrides`)
- `src/lib/buvis/pybase/configuration/loader.py` (`merge_configs`)
- `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] lib: warn on keys that are not fields of the settings model - Acceptance: the three repro cases warn, valid configs stay silent for every tool's shipped defaults.
- [ ] CHANGELOG `Changed` entry.

## Test Strategy

### Critical Scenarios

Regression test, failing against current code first. Evidence from the run, verbatim:

```
- `sources: [a]` plus `sorces+: [b]` gave rc=0, and only skill-a linked.
- `config_root: /x` gave rc=0.
- `srouces:` alone gave the generic `no skill sources configured` message.
```

## Risks

- A shared-library warning may fire on existing configs across tools, or on keys other tools read on purpose. Run each tool's default config through it before merging.
