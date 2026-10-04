# Surface the meta-budget share in postup

<!-- requirements; migrated from PRD 00072 flat file -->

## Overview

### Problem Statement

The operator has a meta-budget policy (meta <= 30% of monthly spend) but no
surface that computes or shows it. The portfolio brief is the natural home;
brief-portfolio (the skill) is retiring into postup, so the metric belongs in
postup's brief views, not the dying skill.

### Target Users

Solo operator reading the monthly portfolio brief.

### Success Metrics

- The brief shows meta-share of spend for the trailing 30 days as a percentage
  with a green/red state at the 30% ceiling.
- Attribution rule implemented: sessions in `~/.claude` count as meta;
  sessions in released-plugin repos (buvis marketplace members) count as
  product; everything else counts as product.
- Metric renders "n/a" gracefully when cost data is absent for the window.

## Functional Decomposition

### Capability: Meta-share metric

#### Feature: Compute meta share
- **Description**: trailing-30-day meta vs total spend from the cost ledger.
- **Inputs**: `~/.local/share/agents/metrics/costs.jsonl` (written by
  `track_cost.py`). Premise RE-CHECKED 2026-09-30 against the live ledger + the
  writer source, and the PRD's original assumptions were WRONG on two points,
  now corrected here:
  1. **Path migrated.** The ledger is at `~/.local/share/agents/metrics/`, not
     the `~/.claude/metrics/` in the original draft (same agents-relocation
     effort 00085 tracked). `track_cost.py:30-31` is authoritative.
  2. **Rows carry no project/cwd field.** Verified schema per row:
     `{host, ts, sid, model, tier, cumulative, [nested], in, cache_write,
     cache_read, out, cost_usd}`. Attribution is therefore NOT possible from
     the ledger alone — it requires the documented **sid→transcript-dir join**:
     Claude stores transcripts at `~/.claude/projects/<encoded-cwd>/<sid>.jsonl`
     where the dir name is the session's cwd with `/`→`-` (e.g.
     `-Users-bob--claude` = `/Users/bob/.claude`). The collector globs
     `~/.claude/projects/*/<sid>.jsonl`, decodes the parent dir back to a cwd,
     and classifies. Document this join in the collector docstring. Both paths
     (ledger dir, transcripts dir) must be config-overridable, not hardcoded.
  - Rows are **cumulative per sid** (`cumulative:true`) — the running total as
    of that Stop, so per-sid spend is the MAX (last) `cost_usd` for that sid in
    the window, NOT the sum of its rows. Summing rows double-counts.
- **Outputs**: `{meta_pct, total_usd, window_days}` in postup's data layer.
- **Behavior**: attribution per the Success Metrics rule; unknown-project rows
  count as product (never inflate meta silently).

#### Feature: Render with ceiling state
- **Description**: one brief tile/line: "meta 27% of $X (30d)" green under
  30%, red at or above.
- **Inputs**: the computed metric; ceiling constant 30 (config-overridable).
- **Outputs**: brief view element (web + TUI text brief).
- **Behavior**: absent data renders "meta n/a", never an error.
