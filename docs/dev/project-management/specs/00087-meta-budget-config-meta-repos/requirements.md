# Count configured Claude-tooling repos as meta in postup's meta-budget

<!-- requirements; migrated from PRD 00087 flat file -->

## Overview

### Problem Statement

00072's attribution counts only sessions under `~/.claude` as meta. The operator
also considers work in specific Claude-tooling repos to be meta, but the metric
has no way to say so — the rule is a fixed two-way split (`~/.claude` vs
everything-else-is-product). The meta share therefore under-reports the
operator's real meta spend (~3.2% vs a true figure that includes the tooling
repos).

### Target Users

Solo operator reading the monthly portfolio brief / web tile.

### Success Metrics

- The meta attribution additionally counts sessions whose cwd is **at or under
  any configured meta-repo root** as meta, alongside `~/.claude`.
- The meta-repo set is **config-driven** (a `meta_repos` list of absolute repo
  paths in postup settings — YAML/env-overridable like `roots`), NOT a name
  pattern. Empty by default, so the metric is unchanged for anyone who does not
  configure it (back-compatible with 00072 behavior).
- With the three operator-named repos configured
  (`~/git/src/github.com/buvis/{claude-autopilot,agent-skills,agent-plugins}`),
  the live meta share rises from ~3.2% to the sum of `~/.claude` + those repos'
  attributed spend.
- Unknown / unlisted sessions still count as product (meta is never silently
  inflated — the 00072 invariant holds).
- Metric still renders "n/a" gracefully when cost data is absent.

## Functional Decomposition

### Capability: Config-driven meta attribution

#### Feature: Multi-root meta classification
- **Description**: classify a session as meta when its transcript cwd is at or
  under `~/.claude` **or** any configured meta-repo root.
- **Inputs**: the existing sid→transcript join (unchanged); a new
  `meta_repos: list[Path]` argument to `collect` (defaults to empty). Each entry
  is encoded with the SAME `_encode_cwd` transform (`/`→`-` AND `.`→`-`) used for
  the `~/.claude` meta root, and matched in encoded space (`name == prefix or
  name.startswith(prefix + "-")`) exactly as the existing `~/.claude` prefix is —
  so a repo path containing a literal `.` (e.g. `github.com`) matches correctly.
- **Outputs**: unchanged `MetaShare` shape; `meta_usd`/`meta_pct` now include the
  configured repos.
- **Behavior**: `_is_meta_sid` tests the sid's transcript dir against the set of
  encoded prefixes `{~/.claude} ∪ meta_repos`; a hit on ANY prefix is meta. No
  transcript, or a cwd under none of the prefixes → product. Order-independent.

#### Feature: `meta_repos` setting
- **Description**: a `PostupSettings.meta_repos: list[str]` field threading the
  configured absolute repo roots to `collect` at both call sites (the `collect`
  command's data.json snapshot and the live text-brief read).
- **Inputs**: YAML config / `BUVIS_POSTUP_META_REPOS` env / CLI (same layering as
  `roots`).
- **Outputs**: the list, expanded (`~` and relative resolved to absolute) before
  it reaches `collect`.
- **Behavior**: empty default = 00072 behavior unchanged. Both call sites
  (`commands/collect/collect.py`, `commands/brief/brief.py`) pass
  `meta_repos=[Path(p).expanduser() for p in settings.meta_repos]`.
