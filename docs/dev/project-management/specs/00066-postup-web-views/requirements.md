# postup D: web frontend views (Matrix/Activity/Work/PRDs + temporal features)

<!-- requirements; migrated from PRD 00066 flat file -->

## Overview

### Problem Statement
00065 lands the skeleton and core tabs; the SPA's remaining surface — Matrix, Activity, Work, PRDs tabs, RepoDetail, the attention Horizon, the since-last diff, and the trend sparkline — still has no home. This PRD completes web feature parity with the skill's SPA.

### Target Users
Solo developer triaging the portfolio: urgency/importance matrix, recent activity, in-flight work, PRD pipeline, and per-repo drill-down.

### Success Metrics
- All seven SPA tabs exist (Brief/Todos/Repos from 00065 + Matrix/Activity/Work/PRDs) plus RepoDetail.
- Attention Horizon, since-last diff, and trend sparkline render from fixture payloads (`data-prev.json`, `history.jsonl`).
- Every view has a component test; CHANGELOG Added entry; gems gates green.

## Functional Decomposition

### Capability: Extended views
The remaining tabs and the drill-down.

#### Feature: Matrix view
- **Description**: Judgment todos plotted by importance/effort with urgency signal (the SPA's prioritization matrix).
- **Inputs**: Derived todos (00064 schema fields: urgency, importance/effort).
- **Outputs**: Matrix tab.
- **Behavior**: Todos without judgment fields (deterministic-only mode) fall back to a mechanical-todos list with an "not enriched" cue.

#### Feature: Activity view
- **Description**: Portfolio-wide recent activity (commits, releases, CI, PRs/issues) ordered by recency.
- **Inputs**: Per-repo signals from the payload.
- **Outputs**: Activity tab.
- **Behavior**: Aggregates across repos; per-repo `errors[]` render as inline badges, not gaps.

#### Feature: Work view
- **Description**: In-flight work: dirty/ahead-behind/stash state, stray branches/worktrees, review-requested/authored PRs.
- **Inputs**: Local-state + external-review signals.
- **Outputs**: Work tab.
- **Behavior**: Groups by repo; empty state says "clean" rather than rendering nothing.

#### Feature: PRDs view
- **Description**: PRD pipeline counts per repo (`backlog/wip/done`).
- **Inputs**: PRD pipeline signals.
- **Outputs**: PRDs tab.
- **Behavior**: Repos without a `dev/local/prds/` tree are omitted, not zero-filled.

#### Feature: RepoDetail
- **Description**: Per-repo drill-down combining all of that repo's signals.
- **Inputs**: One repo's slice of the payload.
- **Outputs**: Detail route reachable from Repos/Activity/Work.
- **Behavior**: Shows the repo's `errors[]` verbatim so degraded collection is visible exactly where it happened.

### Capability: Temporal features
What changed and where it is heading.

#### Feature: Attention Horizon
- **Description**: The SPA's attention queue surfaced as a ranked horizon across the portfolio.
- **Inputs**: Derive layer's attention queue.
- **Outputs**: Horizon strip/section on the Brief.
- **Behavior**: Ranking logic lives in `derive` (ported in 00065) — this feature only presents it.

#### Feature: Since-last diff
- **Description**: What changed since the previous collect run.
- **Inputs**: `data.json` vs `data-prev.json`.
- **Outputs**: Diff badges/sections on Brief and Repos.
- **Behavior**: Diff computed in the derive layer against the rotated previous payload; first run (no prev) renders without diff markers.

#### Feature: Trend sparkline
- **Description**: Portfolio trend over time.
- **Inputs**: `history.jsonl` lines.
- **Outputs**: Sparkline on the Brief.
- **Behavior**: Renders from whatever history exists (fresh start acceptable per discovery — no legacy migration); a single data point renders as a dot, not an error.
