# Founding documents audit - second reviewer (2026-08-05)

Independent audit of `docs/reference/` against every input document still in
`~/bim/reference/local/10-projects/20251111171017-create-documents-into-zettelkasten-claude-skill/`.

## Sources checked

| Input | Extracted into foundations? |
|---|---|
| `20260411115243-idea-reboot/system-architecture.md` (69 KB) | superseded by the reviewed copy below |
| `20260411134500-initial-design-review/system-architecture.md` (89 KB) | partially - see gaps |
| `20260411115243-idea-reboot/system-design-proposal-by-perplexity.md` | trail-format candidate only |
| `20260411115243-idea-reboot/example-use-cases.md` | yes, as use-case seeds |
| `20260412113845-build-001-refinement-using-former-feedback/former-solution-feedback.md` | yes, as requirement seeds |
| `backups/skill-bkp-01/02/03` (the `zettelmaster` builds) | yes, as anti-patterns |
| `test-01-generated-notes/` (165 files, real output of attempt #1) | **no** |
| `zettel-strucutre/input/` (~800 real bim zettels) | format lineage only |

## Verdict

The foundation set is sound and the autonomy rework was the right call. Nothing
load-bearing was lost from the philosophy or the Karpathy pattern. Five defects
are internal to the spec and should be fixed before requirements; seven gaps are
open design decisions that belong in the elicitation.

## Minutes (2026-08-05)

| # | Severity | Finding | Decision | Status |
|---|---|---|---|---|
| D3 | HIGH | Aporia zettels restate both disagreeing claims, polluting the claim set the detector reads | Aporia zettels carry no claims; reference both sides via `contradicts` + targeted `disagreement` doubt | Applied, spec 7.5 / 7.6 / 13 |
| D6 | HIGH | A doubt cannot address a claim in another zettel, so spec 7.6's structural-aporia derivation was unimplementable (surfaced while fixing D3) | Add optional `target` (`to` + `claim`) to doubt entries | Applied, spec 5.3 / 7.6 / 13 |
| D1 | HIGH | Supersession expressible only by ambiguous composition (`rejected` + symmetric `contradicts`) | Swap `questions` for `supersedes`; cap of ten holds because a targeted doubt now covers `questions` | Applied, spec 8 |
| D4 | MEDIUM | Automatic assent/lifecycle transitions reset `processed`, driving it to permanently `false` under autonomy | Reset only on claims/doubts changes | Applied, spec 7.7 / 13 |
| D2 | LOW | `generalizes` named as an inverse but absent from the vocabulary | `exemplifies` marked asymmetric | Applied, spec 8 |
| D5a | LOW | No transitivity or cycle rule on relations | Transitive column added; cycles forbidden on the three transitive relations | Applied, spec 8 |
| D5b | LOW | Pruning exempts `rejected` but not `delivered-as` | Both exempt | Applied, spec 7.3 |
| D5c | LOW | Voice configuration is a dangling dependency | Already an open question in the discovery doc | Queued (G7) |
| - | INFO | Prior build's real output not in the reference set | Added `docs/reference/anti-example-prior-build-output.md` | Applied |
| G1-G5, G7 | - | MOC/trail format, search, index.md/log.md, capture, voice config | Already carried by the discovery doc's elicitation (Q1-Q9) and open questions | No action |
| G6 | MEDIUM | Claim index needs parent `assent` or the detector re-litigates settled questions | Queued as an open question | Queued |
| G4 | LOW | Trails may not survive autonomy; nothing in v1 writes one | Queued as an open question | Queued |
| J | - | Type vocabulary sized for the wrong vault | Resolved independently in parallel session | Applied, commit 41af6a3 |

## Confirmed preserved (no action)

- Anti-patterns from attempt #1: all nine survive in `lessons-from-prior-iterations.md`.
- Feedback-round seeds: noise-filter style, relation-completeness pass, integration-over-creation.
- Success criteria: six, correctly re-scoped for autonomy.
- Hard separation from `~/bim`: enforced structurally by spec 10.4 (absolute root,
  `..` rejected, every path must resolve under root). The constraint has a mechanism,
  not just a promise.
- `synthetic: true` (legacy mandatory field) dropped deliberately and correctly:
  under Klyreon every zettel is LLM-authored, so the flag is constant-true.
  Absence of `processed` now signals user-authored.
- Legacy `hub` / `toc` zettel types replaced by `wiki/mocs/`. Legacy dataview
  reference-section relations replaced by frontmatter `links`. Both noted in the spec.

## Defects in the spec (fix before requirements)

### D1 - Supersession is expressible only by ambiguous composition (HIGH)

Contradiction detection is the primary capability. The prior design resolved every
detected conflict into one of three shapes: **aporia**, **supersede**, **refine**.
The spec can express aporia (`disagreement` doubts + `contradicts` link) and refine
(`narrower-than`), but supersede has no recorded form: no `superseded-by` field, no
`supersedes` relation, and the ten-relation cap is full.

What survives is composition: old zettel goes `assent: rejected` and carries a
`contradicts` link to the new one. That is inferable but ambiguous - `contradicts`
is symmetric and carries no direction of replacement, and `rejected` does not say
*why*. Lint's "claims superseded by newer sources" check (named in Karpathy's doc
and in the lessons doc) has nothing unambiguous to query.

Cheapest honest fix: write the inference rule into the spec so the CLI and lint
agree, rather than adding a field.

### D2 - `generalizes` is named as an inverse but is not in the vocabulary (MEDIUM)

Spec 8, relation table: `exemplifies` lists inverse `generalizes`. `generalizes` is
not one of the ten rows. `broader-than`/`narrower-than` are both rows and mutual
inverses, so the table is inconsistent with itself. A validator built from the table
will reject a link a reader of the same table would write.

### D3 - Aporia zettels restating claims pollute the claim set (HIGH)

Spec 7.5: "aporia zettels usually carry the two claims that disagree". The claim set
is simultaneously the contradiction detector's index and the dedup index. Restating
both sides of a conflict inside a third zettel means:

- every later ingest re-detects the same contradiction against the aporia's copies;
- dedup sees near-duplicate claims and proposes strengthen/same-as on them.

The mechanism that records a resolved conflict feeds the detector that found it.

### D4 - `processed` reset contradicts the autonomy rework (MEDIUM)

Spec 7.7 resets `processed: false` whenever an automated operation changes claims,
doubts, assent, or lifecycle. Spec 7.2 and 7.3 make assent and lifecycle transitions
rule-driven and automatic. Every maintenance pass therefore un-reviews previously
reviewed zettels. The flag converges on permanently `false`, and its only consumer
(query/delivery tie-break) stops discriminating. The second-pass autonomy audit
changed 7.2 and 7.3 but left 7.7's reset trigger untouched.

### D5 - small holes (LOW)

- No transitivity or acyclicity rule on relations. `broader-than`, `narrower-than`,
  and `requires` are transitive; nothing forbids a cycle, and a `broader-than` cycle
  silently breaks any hierarchy walk. Attempt #1's relations doc marked OWL
  properties explicitly; the cap-at-ten rewrite kept the `Inverse` column and dropped
  transitivity.
- Pruning exempts `rejected` zettels but not zettels carrying `delivered-as`.
  Deleting one breaks the provenance of a shipped deliverable.
- Voice configuration is a dangling dependency: paraphrase is a MUST in 11.5 and 13,
  the artifact that defines the voice does not exist and its location is deferred.

## Gaps to queue for elicitation

### G1 - MOCs and trails are ungoverned file species (MEDIUM)

Spec 1: "There are **two file species** governed by this spec." MOC and trail files
are neither. Spec 3.1 gives them a location and a filename rule and explicitly defers
their internal format. Consequences: MOC `id` falls through spec 5.1 (which covers
only 14-digit zettels/trails and kebab-case source documents), and MOC frontmatter is
entirely unspecified.

This matters more than "open question" suggests: MOC membership drives the orphan
check, the orphan check drives pruning, and pruning **deletes files**. A delete path
currently depends on an unspecified format.

### G2 - No position on search or retrieval

The prior design settled `qmd` as the single external dependency, with a
`Read`+`Grep` fallback below ~100 notes. The foundation set carries nothing. The
claims layer replaces retrieval for contradiction detection, but body-level query at
several thousand notes still needs an answer, even if the answer is "grep, revisit
at scale".

### G3 - `index.md` and `log.md` dropped without a decision

Both are load-bearing in Karpathy's pattern: `index.md` is the anti-RAG retrieval
mechanism ("the LLM reads the index first"), `log.md` is the chronological journal
that tells the LLM what it recently did and is the substrate for the morning-digest
use case. The spec defers both to operational design; the lessons doc mentions
neither. The claims layer arguably replaces `index.md`. Nothing replaces `log.md`.

### G4 - Do trails survive autonomy?

Trails were the output of interactive query and Socratic sessions. Under
mostly-autonomous operation nothing obviously writes them. Either they become the
autonomous-run journal (merging with `log.md`) or they are vestigial - yet
`wiki/trails/` is still mandated in the root layout (spec 10.2).

### G5 - Capture is unspecified

The front door of the system. Spec 2.3 says source documents are "created by capture
step (clipper, paste, transcript download)" and stops. In a mostly-autonomous system
capture is the one place a human must act every time, so it is the highest-value UX
surface of the CLI and has no requirement behind it.

### G6 - The claim index needs assent context

`rejected` zettels stay in the wiki and keep their claims. Contradiction detection
must distinguish "conflicts with a claim I endorse" from "conflicts with a claim I
already refuted", or it will re-litigate settled questions on every ingest. The
format supports it (assent lives on the parent zettel); no requirement says the claim
index must carry it.

## Evidence supporting the already-queued type-vocabulary question

The zettel `type` vocabulary (~23 values) was inherited from the manual bim vault.
Measured distribution across the 800-zettel corpus:

| type | count | | type | count |
|---|---|---|---|---|
| `project` | 332 | | `wiki-article` | 36 |
| `note` | 165 | | `cheatsheet` | 14 |
| `meeting-minutes` | 61 | | `course` | 13 |
| `list` | 43 | | `recipe` | 10 |
| `definition` | 43 | | `snippet` | 8 |
| `procedure` | 40 | | everything else | <5 each |

41% `project` plus 8% `meeting-minutes`: bim is a work tracker with a knowledge
annex. Klyreon is a research wiki, hard-separated from bim, so `budget`,
`meter-reading`, `poem`, `joke`, `itinerary`, `project-tracker` and probably
`recipe` will never be written there. The vocabulary is sized for the wrong vault.

## Recommended addition to the reference set

`test-01-generated-notes/` is the real output of attempt #1 and is not in the
foundation set. Measured: 165 files, **58 with no YAML frontmatter at all**, no
zettel IDs, no atomicity (a single "Graph RAG" file runs 412 lines with 11 H2
sections), hand-rolled `[<- Back to Index]` navigation instead of links, and exactly
the corporate-presentation prose the feedback round banned.

The lessons doc states the anti-patterns abstractly. One representative artifact
makes "do not produce this" checkable instead of aspirational, and gives the
acceptance criteria for noise filtering and atomicity something concrete to fail
against.
