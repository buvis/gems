# Founding documents review - minutes (2026-08-05)

Reviewed set (docs/reference/): original-karpathy-idea-proposal.md, zettel-format-specification.md, ancient-philosophy-applied-to-zettelkasten.md. The idea and philosophy docs read clean as vision documents; all actionable findings concerned the format spec.

| # | Severity | Finding | Decision | Status |
|---|----------|---------|----------|--------|
| 1 | CRITICAL | Two spec revisions existed; the user-named one was the older (z-prefixed IDs, doubt: tags, no collision rule, no review tracking) | Adopt newer revision as canonical (14-digit IDs + collision bump, structured claims/doubts, processed/reviewed) | Applied, commit 55c9c14 |
| 2 | HIGH | Six dangling references to excluded system-architecture.md; MOC/trail file formats undefined | Minimal scrub: spec now stands alone as data contract; MOC/trail format + operations named as open questions | Applied, commit 88ca850 |
| 3 | MEDIUM | Zettel `type` vocabulary (~23 types) mirrors the manual bim vault, incl. personal-life types | Queue as dedicated elicitation question | Queued (discovery doc) |
| 4a | LOW | No spec version identifier | Rejected by user | Rejected |
| 4b | LOW | `updated` had no bump rule (breaks 7.7 staleness signal) | Add MUST-bump sentence to 5.2 | Applied, commit 2af111b |
| 4c | LOW | Fresh zettels cite `sources/archive/...` paths that dangle until the source is archived | Record as named open question in spec 3.2 | Applied, commit 2af111b |
| 4d | LOW | 14-digit IDs are local wall-clock; DST/travel can wobble ordering | Note in 3.1: `created` (with offset) is authority for real time | Applied, commit 2af111b |

Queued for elicitation:

- Type vocabulary scope (finding 3).
- Config location: spec hardcodes `~/.claude/klyreon.yaml`, which presumes Claude-owned tooling; decide together with CLI shape (surfaced during review, not a decided finding).
- Ingest MUST actively seek relations and MOC anchors: connection density is an ops mandate, not a format property (from the complexity-removal pressure test).
- Maintenance trigger: prior design resolved rework as "human attention is the trigger (daily briefing)" - conflicts with autonomy constraint; maintenance must self-trigger.
- Salvage inputs for discovery: example-use-cases.md (use-case seeds), former-solution-feedback.md (noise-filter style, relation-completeness pass, integration-over-creation), old system-architecture.md sections 16-18 (anti-patterns, success criteria, open questions).

---

# Second pass: autonomy audit (2026-08-05)

User-set constraints: system runs mostly without human intervention; contradiction detection at ingest is the primary capability; pruning against information overload is required; human review must never be necessary to keep the system going.

## Contradictions found and fixed (commit cb55c10)

| # | Was | Now |
|---|-----|-----|
| 1 | 2.4/5.2/7.7: drafts "await human review"; review session is the only path to `processed: true`; heavy review-tracking section | Review is opportunistic, never a gate; no operation waits for it; 7.7 compacted; user-authored notes may omit the fields |
| 2 | 7.3: "Promotion happens during rework sessions, never automatically" | Promotion and pruning are rule-driven maintenance ops that MAY run automatically; human override wins |
| 3 | No pruning mechanism anywhere | Pruning defined: orphaned, uncorroborated fleeting zettels past a maintenance window are deleted with link cleanup; git history is the archive; `rejected` exempt; thresholds = ops design |
| 4 | Contradiction detection implicit (claims existed for "cross-update") | Named explicitly as THE contradiction detector: single-pass claim-set comparison at ingest; conflicts become `disagreement` doubts, `contradicts` links, or aporia zettels (2.4, 7.5) |
| 5 | Claims SHOULD on assertion-bearing zettels | Claims MUST on `thesis`/`argument`/`observation` - a claim-less assertion is invisible to contradiction detection (5.3, 7.5, 13) |
| 6 | 7.2 assent framed as human act | System applies assent on owner's behalf; rule-driven transitions (corroboration -> accepted, open disagreement holds tentative/unknown); human override wins |
| 7 | Four tag namespaces (`topos:`, `kind:`, `sphere:`, `output:`) | Removed. No consuming operation existed; `output:` duplicated lifecycle+delivered-as; Aristotelian lever now carried by `type`+`concept-type`; lint flags colon-prefixed tags as legacy |
| 8 | 7 concept-types incl. `belief` | `belief` removed (= thesis with `assent: tentative`; overlap caused classification jitter, which degrades claim comparison) |
| 9 | `zettel-ingest` skill / CLAUDE.md voice references | Tool-neutral: "ingest tool", "vault's voice configuration" (location = ops design) |

## Kept deliberately

- `claims`/`doubts` structured fields: load-bearing for the primary capability.
- `aporia` concept-type: the artifact an autonomous system produces when it detects a contradiction it cannot resolve.
- `processed`/`reviewed`: cheap opportunistic signal, matches bim habit; degrades to no-op if human never reviews.
- 10-relation links cap, MOCs, lifecycle, `publish`, collision rule, root-relative paths.

## Practicality / growth / consistency verdict

- Consistent: no remaining human-dependency in any MUST path; every philosophical lever maps to exactly one mechanism.
- Practical: validation surface shrank (no namespace vocabularies, one fewer enum value, -24 net lines); everything machine-checkable by a CLI.
- Growth: claim-set single-pass scales to ~10k notes in current context windows (~400k tokens); beyond that the ops design shards or indexes the claim set - format unaffected. Flat `wiki/notes/` fine at that scale.
- Still open (deliberate): MOC/trail format, type vocabulary scope, config location, archive-path timing.

## Karpathy foundation verdict: SOUND, with amendments

Field reports on the pattern (widely replicated through 2026) confirm the core loop (immutable sources -> LLM-maintained wiki -> compounding synthesis) and name four failure modes, each answered here: (1) scale ceiling when wiki outgrows context -> claims layer; (2) error propagation across linked pages -> contradiction detection at ingest + doubts + lint; (3) maintenance collapses when the human disengages -> autonomy-first operations, review opportunistic; (4) ingest cost -> acceptable at personal scale, batching is an ops concern. Amendments vs. Karpathy's original: no human-in-the-loop per ingest, zettel+claims structure instead of free-form wiki pages, and hard separation from the manual vault.
