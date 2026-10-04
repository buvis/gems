# SPA → postup web parity sweep (PRD 00066)

- **Date:** 2026-09-28
- **PRD:** 00066 (postup D — web frontend views pt.2 + temporal features)
- **Method:** per-component checklist against the brief-portfolio SPA source
  (`~/.claude/skills/brief-portfolio/app/src/`), mapping every SPA component's
  *information content* to a postup SvelteKit view. Visual parity is informal
  (PRD + discovery Q9); this sweep tracks information content only.
- **Scope note:** 00065 shipped Brief/Todos/Repos + the derive/payload/done
  logic layer. This PRD adds Matrix/Activity/Work/PRDs, RepoDetail, and the
  temporal features (Horizon strip, since-last diff, trend sparkline). Rows for
  00065-owned components are included for completeness and marked as such.

## Deliberate, PRD-sanctioned differences (apply to several rows below)

1. **No d3-force gravity field.** The SPA `Horizon.svelte` is a d3-force
   constellation; d3-force is not in the pinned toolchain and the PRD forbids
   bumping it. The PRD names the feature an "Attention **Horizon strip**", so
   the postup Horizon presents the same ranked attention queue
   (`attentionHorizon`) as a strip. Information content (which repos need you,
   score, severity, top reason) is preserved; the physics visualisation is not.
2. **Navigation instead of `onselect`/modal.** The SPA drives a right-side
   `RepoDetail` drawer via an `onselect` callback and a `tip`/`slots` context.
   postup follows the 00065 SvelteKit convention: drill-down is a real route
   (`/repo/[owner/name]`) reached by `<a>` links; org-colour `slots` dots and
   the hover `tip` are cosmetic and dropped (they carried no information).
3. **Org filter is not re-added.** The SPA App.svelte has an org filter chip.
   00065 did not port it and 00066 does not add it — out of scope; every view
   renders the whole portfolio. No information is lost (all repos shown).

## Per-component checklist

| SPA component | Information content | postup home | Status | Notes |
|---|---|---|---|---|
| `App.svelte` (shell, tabs, counts, org filter) | 7-tab nav + per-tab counts; generated-at + window; storage-blocked notice | `routes/+layout.svelte` | ✅ full (counts) / ⚠ org filter dropped | All 7 tabs + counts (todos/matrix-do/repos/activity/work/prds) wired. Org filter intentionally omitted (diff #3). |
| `Brief.svelte` — stat row | repos/burning + commits/PRs/issues/failing CI/security/PRD backlog/releases/local-WIP | `routes/+page.svelte` | ✅ full (00065 + this PRD) | Stat tiles present since 00065; unchanged. |
| `Brief.svelte` — quick wins | first N quick-effort open todos | `routes/+page.svelte` | ✅ full (00065) | `quickWins`. |
| `Brief.svelte` — burning now | top attention-scored repos + top reason | `routes/+page.svelte` | ✅ full (00065) | inline `queue`. |
| `Brief.svelte` — story/epics | narrative paragraphs + per-repo epic groups | `routes/+page.svelte` | ✅ full (00065) | not-enriched empty-state kept. |
| `Brief.svelte` — **since-last diff** | vs prev: cleared/new counts + top movers | `routes/+page.svelte` "Since last brief" | ✅ **this PRD** | `diffSinceLast`; no-prev → section omitted. |
| `Brief.svelte` — **trend sparkline** | open-items series across complete briefs | `routes/+page.svelte` `Sparkline` | ✅ **this PRD** | `trendSeries` (drops incomplete runs); single point → dot. |
| `Horizon.svelte` | ranked attention queue (which repos need you, score, severity, reasons) | `routes/_components/Horizon.svelte` on Brief | ✅ **this PRD** (info) / ⚠ visual | Strip, not gravity field (diff #1). |
| `Sparkline.svelte` | polyline of a numeric series | `routes/_components/Sparkline.svelte` | ✅ **this PRD** | single point → dot (PRD edge case). |
| `Strip.svelte` | horizontal-scroll affordance (edge fades/chevrons) | — | ➖ not ported | Pure layout chrome, zero information content; strips render as plain flex lists. |
| `Icon.svelte` | inline SVG glyphs | — | ➖ not ported | Decorative; replaced by text/unicode marks. No information lost. |
| `Todos.svelte` | urgency-grouped todo list, done-toggle, hide-done | `routes/todos/+page.svelte` | ✅ full (00065) | unchanged. |
| `Matrix.svelte` | Eisenhower quadrants (do/schedule/delegate/drop) from `allTodos`+`quadrant`; deterministic-only fallback | `routes/matrix/+page.svelte` | ✅ **this PRD** | 4 quadrants; **"not enriched · mechanical todos only"** cue when epics absent. |
| `Repos.svelte` | repo cards: score, badges (CI/PRs/issues/security/unreleased/WIP/backlog), errors, filter/sort | `routes/repos/+page.svelte` | ✅ full (00065) + **since-last badge** (this PRD) | Added per-card score-delta badge (no-prev → none) + drill-down link. |
| `Activity.svelte` — commit heat | weekly-bin heatmap per active repo + month axis | `routes/activity/+page.svelte` | ✅ **this PRD** | `weeklyBins`/`weekStart`/`monthLabels` ported. |
| `Activity.svelte` — recent releases | releases table by recency | `routes/activity/+page.svelte` | ✅ **this PRD** | most-recent-first. |
| `Activity.svelte` — errors surfacing | (SPA left CI-missing note only) | `routes/activity/+page.svelte` | ✅ **this PRD, extended** | PRD requires per-repo `errors[]` as **inline badges, not gaps** — added a "Collection warnings" badge row. |
| `Work.svelte` — external PRs | review-requested / authored, error state | `routes/work/+page.svelte` | ✅ **this PRD** | error → inline message. |
| `Work.svelte` — open PRs / issues / CI wall | in-flight PRs, issues, CI runs | `routes/work/+page.svelte` | ✅ **this PRD, regrouped** | PRD requires **group by repo** + **"clean" empty state**; postup groups local WIP + branch/worktree litter + open PRs per repo. Flat issue/CI-wall tables folded into the per-repo cards (issues live on RepoDetail; CI wall on RepoDetail). |
| `Prds.svelte` | per-repo backlog/wip/done counts; omit repos w/o tree | `routes/prds/+page.svelte` | ✅ **this PRD** | repos with `prds:null` or empty tree omitted (not zero-filled). |
| `RepoDetail.svelte` | one repo's full slice: meta, local state, attention reasons, **errors verbatim**, security, commits/epics, CI, PRs, issues, releases, PRDs, branch litter | `routes/repo/[...name]/RepoDetail.svelte` | ✅ **this PRD** | `errors[]` rendered VERBATIM; reachable from Repos/Activity/Work links. Focus-trap/modal chrome dropped (it is a route now). |

## Coverage of PRD-named behaviours

- Matrix deterministic-only fallback → cue + mechanical list. ✅ tested
  (`routes/matrix/page.svelte.test.js`).
- Activity `errors[]` inline badges, not gaps. ✅ tested
  (`routes/activity/page.svelte.test.js`).
- Work group-by-repo + "clean" empty state. ✅ tested
  (`routes/work/page.svelte.test.js`).
- PRDs omit repos without a prds tree. ✅ tested
  (`routes/prds/page.svelte.test.js`).
- RepoDetail errors verbatim. ✅ tested
  (`routes/repo/[...name]/RepoDetail.svelte.test.js`).
- Attention Horizon strip presents derive's queue. ✅ tested (Horizon +
  Brief tests).
- Since-last diff on Brief + Repos; no-prev → no markers. ✅ tested (Brief +
  Repos tests).
- Trend sparkline; single point → dot, thin history not an error. ✅ tested
  (Sparkline + Brief tests).

## Blind spots / follow-ups (not blocking this PRD)

- **Org filter** and **org-colour slots**: SPA affordances not ported (diff
  #2/#3). If multi-org filtering is wanted on the web, it is a small follow-up
  (add an org derive + a filter chip in the layout); no data is missing today.
- **Commit-heat hover tooltips**: SPA used a `tip` context for per-cell
  tooltips; postup encodes the same fact in each cell's `aria-label`
  ("N commits, week of …") rather than a hover panel.
- **d3-force Horizon**: if the gravity-field visual is later wanted, it needs a
  `d3-force` dependency decision (out of this PRD's pinned toolchain) — the
  information is already fully present in the strip.
- **SSE refresh / collect-from-UI**: explicitly PRD 00067 scope; nothing here
  depends on a server.
