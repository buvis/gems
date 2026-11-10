---
design: skip
default_model: sonnet
model_tier_rationale: one extra directory check in the loader; repro given verbatim
---

# Config must not load from a world-writable directory

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 9 of 13, LOW, lane trudy.

## Overview

### Problem Statement

`_is_world_writable` in `loader.py` checks only the file mode, not its directory. `~/.local/.config/buvis`, or a symlink to a world-writable directory, is trusted even at mode 0777, so another local user who can write there can feed braid `sources`. Only a 0666 file warns, and it still loads. Exploitable only on a multi-user machine with a misconfigured directory; stable.

### Target Users

Users on shared (multi-user) machines.

### Success Metrics

- A config file inside a directory that is world-writable (resolved through symlinks, no sticky bit) is refused with a console error naming the directory.
- A world-writable file keeps its current warning.
- A normal 0755/0700 directory loads as before.

## Functional Decomposition

### Capability: Directory trust check

#### Feature: Refuse world-writable directories

- Resolve the parent directory, and refuse to load from it when it is world-writable without the sticky bit. Keep the warning for world-writable files. Chosen option: agoge option 2 for directories.

## Structural Decomposition

- `src/lib/buvis/pybase/configuration/loader.py` (`_is_world_writable`)
- `docs/source/configuration.rst`, `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] lib: refuse config from a world-writable directory - Acceptance: both repro setups refuse and print no `WOULD LINK`.
- [ ] Docs and CHANGELOG `Fixed` entry (security).

## Test Strategy

### Critical Scenarios

Regression test, failing against current code first. Evidence from the run, verbatim:

```
- Directory mode 0777 holding a 0644 `buvis-braid.yaml` with `sources: [evil]`: braid printed `WOULD LINK .../.claude/skills/attacker-marker-skill`, with no warning.
- A directory symlinked to a 0777 drop: the same result.
- Only a 0666 file triggered a warning, and that file still loaded.
```

## Risks

- May block a shared-mount setup; a single-user Mac rarely has this exposure, so the cost is the main argument against.
