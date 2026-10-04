# Count configured Claude-tooling repos as meta in postup's meta-budget

<!-- design; migrated from PRD 00087 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/postup/
├── domain/meta_share.py              # Maps to: Multi-root meta classification
├── settings.py                       # Maps to: meta_repos setting
├── commands/collect/collect.py       # Maps to: pass meta_repos (snapshot path)
└── commands/brief/brief.py           # Maps to: pass meta_repos (live-read path)
```

### Module: postup.domain.meta_share
- **Maps to capability**: Config-driven meta attribution
- **Responsibility**: extend `collect` + `_is_meta_sid` to a set of meta
  prefixes; keep the function pure and UI-free.
- **Exports**: `collect(window_days=30, *, ..., meta_repos: list[Path] | None = None)`

### Module: postup.settings
- **Maps to capability**: `meta_repos` setting
- **Responsibility**: carry the configured meta-repo roots in the validated
  settings contract.
- **Exports**: `PostupSettings.meta_repos: list[str]`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies — built first (00072 already landed; master carries meta_share).

- **meta_share multi-root classification**: pure change to the collector.

### Core Layer (Phase 1)
- **settings + call-site wiring**: Depends on [Phase 0].

### Integration Layer (Phase 2)
- none (two-phase PRD; heading retained per template).

## Test Strategy

### Critical Scenarios
- **Happy path**: fixture ledger + a session whose transcript cwd is a configured
  meta-repo → that spend counts as meta.
- **Back-compat**: `meta_repos=[]` → identical result to 00072 (same fixtures).
- **Dotted path**: a configured repo path containing `.` (github.com-style)
  classifies correctly in encoded space.
- **Unlisted**: a repo NOT in `meta_repos` and not under `~/.claude` → product.
- **Error case**: costs.jsonl missing → "meta n/a", no crash (unchanged).

## Risks

- **Config drift** (a repo moves/renames): the allowlist is explicit absolute
  paths; a stale entry simply stops matching (no silent meta inflation). The
  operator maintains the list. Accepted — this was the deliberate choice over a
  fragile `claude-*`/`agent-*` name heuristic.
- **Operator must configure the three repos**: shipping the mechanism with an
  empty default means the metric is unchanged until the list is set. The three
  decided repos
  (`~/git/src/github.com/buvis/{claude-autopilot,agent-skills,agent-plugins}`)
  should be added to the operator's postup config as part of landing this.
