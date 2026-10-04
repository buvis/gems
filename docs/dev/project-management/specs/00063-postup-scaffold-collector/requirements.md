# postup A: gem scaffold + deterministic collector

<!-- requirements; migrated from PRD 00063 flat file -->

## Overview

### Problem Statement
The portfolio status brief lives as a Claude Code skill (`~/.claude/skills/brief-portfolio/scripts/collect.py`, stdlib-only): it runs only inside a Claude Code session and escapes every gems quality attribute (tests, typing, CI, release, docs). This PRD creates the `postup` gem and ports the deterministic collector so the portfolio data pipeline becomes a first-class, tested gem command with typed, versioned file contracts.

### Target Users
Solo developer (Bob) running a portfolio standup across all local repos; the follow-on postup PRDs (00064–00068, 00070, 00072) that consume the gem skeleton and `data.json` contract.

### Success Metrics
- `postup collect` runs on the real portfolio and exits 0 with per-repo failures degraded into `errors[]` (never a crash).
- `data.json` validates against the versioned pydantic contract; all four output files written atomically.
- gems gates green: `pytest -m postup`, ≥50% tool coverage, mypy strict, ruff, CI matrix, Sphinx page, CHANGELOG entry.
- Core-only install (`uv tool install buvis-gems`) runs `postup collect` — zero new runtime dependencies.

## Functional Decomposition

### Capability: Gem scaffold and wiring
Everything that makes `postup` a real gem in the monorepo.

#### Feature: Multi-interface scaffold
- **Description**: Generate the gem via `dev/bin/scaffold.py --multi-interface` and wire it into the repo.
- **Inputs**: Tool name `postup`, description "POrtfolio STandUP".
- **Outputs**: `src/tools/postup/` with `manifest.toml` declaring **cli/tui/rest/web**, `adapters/cli.py` Click entry, `commands/`, `params/`, `settings.py`; console script `postup = postup.adapters.cli:cli`; wheel package + pytest marker registered; CI path filter updated; `docs/source/tools/postup.rst` stub; CHANGELOG Added entry.
- **Behavior**: Scaffold output adjusted only where this PRD's features require; `buvis_options` decorator on the CLI group; lazy imports in command handlers per AGENTS.md.

#### Feature: Postup settings
- **Description**: `PostupSettings(GlobalSettings)` with env prefix and `--config` support (pydantic-settings).
- **Inputs**: Config file / env vars / CLI overrides.
- **Outputs**: Validated settings: `roots` (list of directories to scan), `excludes` (list of repo paths to skip), `out_dir` (output directory), `model` (claude model name, optional, consumed by 00064).
- **Behavior**: `out_dir` defaults to `~/.local/share/postup/` (XDG data dir — decision delegated to this PRD by discovery: fresh start, no legacy migration from `~/.claude/portfolio-brief/`, user-overridable in settings).

### Capability: Repo discovery
Where postup gets its repo list — no gita dependency.

#### Feature: Root-scan discovery
- **Description**: Discover repos by scanning settings-defined roots for `.git`, minus the exclusion list.
- **Inputs**: `roots`, `excludes` from settings.
- **Outputs**: Deduplicated, sorted list of absolute repo paths.
- **Behavior**: A directory containing `.git` is a repo (scan stops descending there); paths listed in `excludes` are dropped; missing/unreadable roots WARN through the console adapter and are skipped.

### Capability: Deterministic collection
Port of `collect.py` behavior under gems discipline.

#### Feature: collect command
- **Description**: `postup collect` gathers all portfolio signals per repo, in parallel, without any LLM.
- **Inputs**: Discovered repo list; `git` CLI; authenticated `gh` CLI; `--no-fetch` flag (skips remote refresh, parity with today's collector flag).
- **Outputs**: `CommandResult`; the four file contracts (below) under `out_dir`.
- **Behavior**: Per repo collect: commits/releases/last-tag/unreleased, issues, PRs, CI runs, security alerts, stray branches/worktrees, PRD pipeline counts (`dev/local/prds/{backlog,wip,done}`), CHANGELOG unreleased section, brush hygiene recency (`dev/local/audit-results/brush-report.md` `generated:` date, drives the 30-day brush-cadence todo), local branch/dirty/ahead-behind/stashes, external review-requested/authored PRs. Repos processed in parallel (bounded workers); any per-repo failure (gh missing/unauthenticated, network, weird repo state) lands in that repo's `errors[]` and WARNs via console — never aborts the run. No `print`/`click.echo`/logging; command class returns failure results instead of exiting.

#### Feature: Versioned file contracts
- **Description**: Typed, versioned on-disk outputs that every other interface consumes.
- **Inputs**: Collected per-repo signals.
- **Outputs**: `data.json` (pydantic-modelled, `schema_version` field), `commits-digest.md` (per-repo commit digest for enrichment), `data-prev.json` (previous run, rotated before write, feeds since-last diff), `history.jsonl` (one appended summary line per run, feeds trend).
- **Behavior**: All writes go through `pybase.filesystem.atomic_write` (00041); rotation order guarantees `data-prev.json` is the prior `data.json` even if the run dies mid-write; unknown `schema_version` on read is rejected loudly.
