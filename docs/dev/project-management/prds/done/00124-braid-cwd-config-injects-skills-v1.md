---
design: skip
default_model: sonnet
model_tier_rationale: one search-path change in braid, repro given verbatim
---

# braid: a cloned repo's buvis-braid.yaml must not inject skills

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 1 of 13, HIGH, lane trudy.

## Overview

### Problem Statement

The config loader reads the current directory as the lowest config layer. Since PRD 00123, braid takes its skill `sources` from that merged config. Running `braid` inside a checked-out untrusted repo links that repo's skills (prompts Claude follows) into `~/.claude/skills`, so they reach every session. The CHANGELOG recommends the `sources+:` shape, which leaves the hole open. It persists until the user notices.

### Target Users

Anyone who runs `braid` with a working directory inside a cloned repo they do not control.

### Success Metrics

- `braid --dry-run` run from inside a directory holding `buvis-braid.yaml` with `sources: [<dir>/evil]` does not print `WOULD LINK` for the skills under `evil`, with or without a home `sources+:`.
- A cwd `claude_root:` no longer redirects the link target for braid.

## Functional Decomposition

### Capability: braid ignores the cwd config layer

#### Feature: Exclude cwd from braid's config search

- Pass braid's config resolution a search path without the current directory (or add a loader flag that skips the cwd layer), chosen by whichever is the smaller change.
- Other tools keep their current search order. Chosen option: exclude cwd for braid only (agoge option 1).

## Structural Decomposition

- `src/tools/braid/` (settings and CLI wiring of the config search path)
- `src/lib/buvis/pybase/configuration/` (only if a loader flag is needed)
- `docs/source/tools/braid.rst`, `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] braid: skip the cwd layer when resolving config - Acceptance: the repro below prints no `WOULD LINK` for the attacker skill.
- [ ] braid: document that braid reads no config from the working directory, add a CHANGELOG `Fixed` entry (security).

## Test Strategy

### Critical Scenarios

Regression test, written to fail against current code first. Evidence from the run, verbatim:

```
The attacker repo holds `buvis-braid.yaml` with `sources: [<repo>/evil]`, and braid runs with cwd inside it.
- Home config uses `sources+: [<legit>]`: `braid --dry-run` printed `WOULD LINK .../homeB/.claude/skills/attacker-marker-skill`.
- No home braid config, `--source <legit>`: the same result.
- A cwd `claude_root:` redirects the link target. This redirect existed before the batch.
- Control: when the home config sets a plain `sources:` key, only the legit skill links.
```

## Risks

- A user who relied on a cwd braid config loses it (unlikely).
- Other tools that link or run things from config (sysup steps) keep the same cwd exposure; dropping the cwd layer for every tool (agoge option 2) may be needed later.
