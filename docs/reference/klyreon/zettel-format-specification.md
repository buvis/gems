# Zettel Format Specification

This document defines the file format used by **Klyreon**, a personal Memex-Zettelkasten grounded in seven ancient knowledge-building disciplines. Any tool that reads, writes, or validates files in Klyreon MUST follow this spec.

The format spec is the contract between the tool layer (ingest, query, lint) and the data layer (Markdown files on disk). It does not describe operations or workflows; those belong to Klyreon's operational design, specified separately (an open item for the requirements phase).

## 1. Scope and conventions

The system stores knowledge as Markdown files with YAML frontmatter. There are **two file species** governed by this spec:

1. **Source documents** (`sources/`): copies of ingested external content (articles, books, quotes, transcripts). They preserve the source's body verbatim or cleaned, and they carry provenance metadata. Source documents are the raw material Klyreon's operations work on. They are NOT zettels.

2. **Zettels** (`wiki/notes/`): atomic notes in the vault's paraphrased voice (LLM-authored under the vault's voice configuration, or written directly by the user). They are produced by ingest of source documents, or written directly by the user. A zettel may be a **concept zettel** (one that carries the concept dimensions described in section 7) or a **utility zettel** (one that does not).

The two species share the same frontmatter conventions (YAML, key naming, ID rule) but use different vocabularies and live in different directories. Both are described below; section 2 explains the distinction in full.

The frontmatter field **`concept-type`** carries the epistemic shape of a concept zettel (thesis, argument, question, etc.). Its name is a compound, distinct from the legacy `type` field, which carries a different and pre-existing meaning (the form of the document: article, note, procedure, etc.). The two are orthogonal: a concept zettel has both, and they answer different questions. All other frontmatter fields use natural unprefixed names because there is no collision to disambiguate.

This spec is paired with a system configuration file at `~/.config/klyreon/config.yaml` that defines the **root**: an absolute path to which all internal paths in zettels and source documents are relative. See section 10.

### 1.1 Philosophical foundation

Klyreon's design is grounded in seven ancient knowledge-building disciplines. Each one shapes a specific part of the format. The format spec implements them through fields, tag namespaces, and body conventions; how each one shapes operations belongs to Klyreon's operational design, specified separately.

These disciplines describe how the writer should think about the material, not who holds the pen. Under Karpathy's LLM Wiki pattern the LLM writes and maintains the wiki; the disciplines below are the discipline the LLM applies while drafting and maintaining. A human may apply the same discipline when reviewing, but no operation depends on that review happening.

| Lever | Implementation in this spec |
|---|---|
| **Socratic** interrogation (the discipline of probing claims) | `claims` field (section 7.5) for the distilled assertions, plus the body template for `concept-type: thesis` and `argument` zettels (Claim, Assumptions, Evidence, Implications). See section 11.3. |
| **Aristotelian** typing (classification by kind) | `type` field (the form, section 6) and `concept-type` field (the epistemic shape, section 7.1). |
| **Stoic** assent (impressions vs. commitments) | `assent` field (section 7.2), applied by the system with rule-driven transitions; a human decision always overrides. |
| **Pyrrhonian Skeptical** five modes of doubt | `doubts` field (section 7.6) with structured entries attached to specific claims or to the whole zettel. |
| **Method of loci** (stable mental places) | Maps of Content (`wiki/mocs/`) as the "rooms" the user mentally traverses. Concept zettels SHOULD link into at least one MOC. See sections 3.1, 5.4. |
| **Commonplacing** (iterative reworking from raw to distilled) | `lifecycle` field with the three states `fleeting`, `literature`, `evergreen`, with rule-driven promotion and pruning. See section 7.3. |
| **Ciceronian** five canons of rhetoric (invention, arrangement, style, memory, delivery) | The `delivered-as` field (section 5.4) records what a zettel has shaped, closing the loop to delivery. |

A note that participates in Klyreon's operations is a **concept zettel** because the result of running these disciplines on raw material is a structured concept, not a passive record. Concept zettels carry the three dimensions (`concept-type`, `assent`, `lifecycle`) plus structured `claims` (required on assertion-bearing shapes) and `doubts` where honest doubt exists (section 7).

Notes that don't carry the concept dimensions are **utility zettels**. They live in the wiki because they are useful (a snippet, a cheatsheet, a procedure), but they don't engage with the philosophical operations. The same file format covers both.

## 2. The two file species

A reader needs to know up front which species a file belongs to, because the validation rules and the meaningful field set differ.

### 2.1 Source documents

**A source document is a Markdown file that holds the full body of one external content item, plus frontmatter that records the item's form and provenance.**

- Lives in `sources/YYYY-MM/` (or `sources/archive/YYYY-MM/` after the derived zettels have been approved).
- Filename is descriptive kebab-case: `article-resilience-patterns.md`, `book-meditations-marcus-aurelius.md`, `quote-aurelius-confine-to-present.md`. Filenames stay readable to match the Web Clipper output and to give the user a recognizable file in `ls`.
- The `id` field equals the filename without `.md`.
- Body is the source's words: the article text, the book chapter, the quoted passage, the transcript. Cleaned of navigation cruft and ads but otherwise unchanged.
- `type` is one of the source-document types (section 6.1): `article`, `book`, `quote`, `transcript`, etc.
- Carries type-specific provenance fields (`article-author`, `article-url`, `book-author`, `book-isbn`, `quote-author`, `quote-source`, etc.).
- Has NO `concept-type`, NO `assent`, NO `lifecycle`. Source documents are raw material; they have not been interrogated yet.

### 2.2 Zettels

**A zettel is an atomic Markdown file that holds one self-contained idea, rendered in the vault's voice.**

- Lives in `wiki/notes/`. The directory is flat: no subdirectories.
- Filename is `YYYYMMDDHHmmSS.md`. Strict format, 14 digits, no prefix, no separators. The ID is the timestamp of creation and never changes. See section 3.1.
- The `id` field equals the filename without `.md`.
- Body is paraphrased and interpreted, not copied from the source. Direct quotation is reserved for cases where exact wording matters (a definition being critiqued, a claim being argued against verbatim).
- `type` is one of the zettel types (section 6.2): `note`, `definition`, `procedure`, `snippet`, etc.
- A **concept zettel** carries `concept-type`, `assent`, and `lifecycle`, carries structured `claims` when its shape asserts something (section 7.5), and carries `doubts` where honest doubt exists. It participates in Klyreon's operations.
- A **utility zettel** has none of those fields and does not participate in the philosophical operations. It is just stored content (a snippet, a cheatsheet, a procedure).
- Tool-drafted zettels carry `processed: false`; a human may flip it in an opportunistic review, and no operation waits for that.
- Concept zettels link to source documents via `sources`, link to other zettels via `links`, and anchor into MOCs via `mocs`.

### 2.3 Comparison

| Aspect | Source document | Zettel |
|---|---|---|
| Lives in | `sources/YYYY-MM/` | `wiki/notes/` |
| Filename pattern | descriptive kebab-case | `YYYYMMDDHHmmSS.md` (14 digits) |
| Body scope | full body of one external item | one atomic idea |
| Body voice | source's words (verbatim or cleaned) | vault voice (paraphrased per the voice configuration) |
| Mutability | immutable (raw layer) | mutable (refined as understanding evolves) |
| `type` field | source-document types: `article`, `book`, `quote`, `transcript` | zettel types: `note`, `definition`, `procedure`, etc. |
| `concept-type`, `claims`, `doubts` | never | optional, present on concept zettels |
| `assent`, `lifecycle` | never | optional, present on concept zettels |
| `processed`, `reviewed` | never | optional, opportunistic human-review markers |
| `links` | rare | common (concept zettels) |
| `mocs` | rare | common (concept zettels) |
| `sources` | rare (only if one capture cites another) | common (concept zettels derived from sources) |
| Created by | capture step (clipper, paste, transcript download) | ingest tool (LLM draft with Socratic interrogation) or direct user authoring |

### 2.4 The living brain

The two species form a loop. The user adds a source document (capture). Ingest applies Socratic interrogation, reads the source, and produces one or more concept zettels in the vault's voice, each with `concept-type`, `claims`, and (if any surfaced) `doubts` set and linked back to the source via `sources`. In the same pass, every new claim is compared against the wiki's existing claim set: conflicts are recorded as `disagreement` doubts, `contradicts` links, or aporia zettels rather than silently coexisting. Drafts land with `processed: false`; a human may review them opportunistically, but the loop never waits for that. As new source documents arrive, existing concept zettels are revisited: claim-level cross-update, contradiction checks, refinement, promotion through the lifecycle, and pruning of fleeting material that never earned survival. The wiki gets richer, not just bigger. Source documents stay frozen in `sources/`; concept zettels evolve in `wiki/notes/`.

## 3. File identity and location

### 3.1 Zettel filenames

Every zettel is a single Markdown file (`.md`) whose filename is:

```text
YYYYMMDDHHmmSS.md
```

- 14 digits: `YYYY` (4) year, `MM` (2) month, `DD` (2) day, `HH` (2) hour 24h, `mm` (2) minute, `SS` (2) second.
- The timestamp is captured in the local timezone of the author at creation. IDs therefore order by local wall-clock time, which can wobble across DST changes or travel; the `created` field, which carries the timezone offset, is the authority for real time. The collision rule below guarantees uniqueness regardless.
- No prefix, no separators. The containing directory (`wiki/notes/` for zettels, `wiki/trails/` for trails) disambiguates species.
- The ID is captured at creation and never changes. Renaming a file breaks every link to it.

Example: `20260411145300.md` is a zettel created on 11 April 2026 at 14:53:00.

**Collision rule.** When a batch operation would produce two zettels in the same second (typical during batch ingest), the second zettel's timestamp is bumped by one second. The bump repeats until the ID is unique. Both the filename and the `created` frontmatter field reflect the bumped value: they always agree. The fidelity loss is bounded by the batch size and keeps the ID as the single source of truth for when the zettel entered the wiki.

Zettels live under `wiki/notes/` relative to the root (section 10). The directory is flat: no subdirectories.

Maps of Content (MOCs) live under `wiki/mocs/` and use kebab-case slugs as filenames (`architecture.md`, `self.md`, `reading-list.md`). Trail files live under `wiki/trails/` with the same compact format: `YYYYMMDDHHmmSS.md`.

The internal format of MOC and trail files is deliberately not specified here yet; it is an open question for Klyreon's requirements. This spec governs only their location and filename rules.

### 3.2 Source document filenames

Source documents use descriptive kebab-case filenames:

```text
<descriptive-kebab-case>.md
```

Examples:

- `article-resilience-patterns.md`
- `book-meditations-marcus-aurelius.md`
- `quote-aurelius-confine-to-present.md`
- `transcript-call-acme-2026-04-11.md`
- `paper-tail-at-scale-dean-barroso.md`

The filename is chosen at capture time and SHOULD remain readable. It usually includes the type (article, book, etc.) followed by a slug derived from the title or source. The `id` field equals the filename without `.md`.

Source documents live under `sources/YYYY-MM/` initially. After the derived zettels have been approved and committed, the source document moves to `sources/archive/YYYY-MM/`. The archived path is what zettels reference, so the link is stable.

Open question for the requirements phase: a zettel created before its source is archived either cites the archive path (dangling until the move) or the live path (broken by the move). The resolution - validator grace for pre-archive paths, cite-live-then-rewrite at archival, or archive-first ingest - is not yet specified.

## 4. Overall layout

Both file species have the same overall layout:

```text
---
<YAML frontmatter>
---

# <H1 title>

<body>
```

The frontmatter is a YAML block delimited by `---` on its own line, top and bottom. The body opens with a single `# H1` whose text MUST match the `title` frontmatter field exactly.

There is no separate "reference" section. Cross-references and external resources live in `links`, `sources`, and `mocs` inside the frontmatter, not in body markup. This is a deliberate departure from the legacy format, which used an Obsidian dataview inline-field block after a trailing horizontal rule.

## 5. Frontmatter

YAML. Keys are lowercase ASCII with dashes where needed. String values are quoted only when YAML requires it (embedded colon, leading special character, etc.). Boolean values are `true` or `false`, never `yes`/`no`.

There are no system-namespace prefixes on field names. The `concept-type` compound name (section 7.1) describes a separate concept from the legacy `type` field; the two coexist on a concept zettel. All other fields use natural names.

### 5.1 Required fields (both species)

These appear on every file regardless of species or `type`.

| Field | Type | Description |
|---|---|---|
| `id` | string | Same as the filename without `.md`. For zettels and trails: `YYYYMMDDHHmmSS` (14 digits, no separators, see section 3.1). For source documents: descriptive kebab-case. Never changes. |
| `title` | string | Declarative title. MUST match the H1 exactly. Make it stand alone in an index entry without context. Quote the whole value if it contains a colon. |
| `created` | ISO 8601 datetime | Creation timestamp with timezone offset, e.g. `2026-04-11T14:53:00+02:00`. Never changes. For zettels, the date/time components MUST match the `id` field exactly. When the collision rule (section 3.1) bumps the ID by a second, `created` is bumped in lockstep so both fields always agree. |
| `type` | enum | The form/kind of the file. For source documents: see section 6.1. For zettels: see section 6.2. |

### 5.2 Common optional fields (both species)

These are present on most files but not required on every one.

| Field | Type | Description |
|---|---|---|
| `updated` | ISO 8601 datetime | Last update timestamp with timezone offset. Any tool that modifies a file's frontmatter or body MUST set `updated` to the modification time (this is what makes the review-staleness signal in section 7.7 computable). Source documents are immutable so this is rare for them. |
| `tags` | list of strings | 3 to 5 tags is typical. See section 9. |
| `publish` | boolean | Owner-controlled signal that the file is safe to expose outside the vault. Tools MAY only ever set this to `false`. |
| `processed` | boolean | Zettels only. `false` on tool-drafted notes that no human has reviewed. `true` after an opportunistic review; review is never required for the system to proceed. Default: `false`. See section 7.7. |
| `reviewed` | ISO 8601 datetime | Zettels only. Timestamp of the most recent human review. Absent until the first review. Set in lockstep with `processed: true`. |

### 5.3 Concept zettel fields (concept zettels only)

These describe the zettel's place in Klyreon's operations. They are OPTIONAL: utility zettels (snippet, cheatsheet, procedure) do not have them. Zettels that participate in epistemic work (concept zettels) carry the three dimensions plus structured claims and doubts as section 7 prescribes.

These fields MUST NOT appear on source documents.

| Field | Type | Description |
|---|---|---|
| `concept-type` | enum | The epistemic shape of the concept. Closed enumeration (section 7.1). The compound name distinguishes it from the legacy `type` field. |
| `assent` | enum | The Stoic state: `accepted`, `tentative`, `rejected`, `unknown`. Section 7.2. Default for new concept zettels is `tentative`. |
| `lifecycle` | enum | The commonplacing state: `fleeting`, `literature`, `evergreen`. Section 7.3. Default for new concept zettels is `fleeting`. |
| `claims` | list of objects | Structured atomic assertions extracted from the zettel body. Each claim has an `id` and a `statement`. Required on assertion-bearing shapes (`thesis`, `argument`, `observation`). See section 7.5. |
| `doubts` | list of objects | Pyrrhonian doubt annotations attached to claims or to the whole zettel. Each doubt has a `mode`, a `claim` reference (or `null`), a `rationale`, and an optional `target` naming a foreign claim. See section 7.6. |

### 5.4 Cross-reference fields

These wire the file into the graph and into the source layer. Source documents typically use only `sources` (and only when one capture cites another). Concept zettels use all four.

| Field | Type | Description |
|---|---|---|
| `sources` | list of strings | Root-relative paths to source documents. Each path MUST resolve under the configured root. Required on concept zettels derived from a source document. |
| `links` | list of objects | Each entry has `rel` (relation, section 8) and `to` (root-relative path to the target zettel). Concept zettels only. |
| `mocs` | list of strings | Root-relative paths to MOC files. Concept zettels SHOULD link into at least one MOC. |
| `delivered-as` | list of strings | Identifiers of deliverables this zettel has shaped (e.g. `blog/resilient-architecture-2026-04`, `rfc/inventory-circuit-breaker`). Concept zettels only. |

### 5.5 Type-specific fields

Some `type` values add their own optional or required fields. These are listed alongside the type vocabulary in section 6.

The most common:

**Source-document types:**

- `article`: `article-author` (string), `article-publication` (string), `article-url` (string)
- `book`: `book-author` (string), `book-isbn` (string), `book-chapter` (string)
- `quote`: `quote-author` (string), `quote-source` (string)
- `transcript`: `transcript-event` (string: meeting, call, interview), `transcript-participants` (list of strings), `transcript-recorded` (ISO 8601 datetime)

**Zettel types:**

- `snippet`: `language` (string: rust, bash, python, etc., matching the fence language)

Type-specific fields that are absent are simply omitted; tools do not require them unless this spec marks them as required.

## 6. The `type` vocabulary

The `type` field describes the form of the file. It is a closed enumeration. Pick the closest fit. Do not invent new values without updating this spec first.

The vocabulary is split into source-document types and zettel types. They do not overlap. Tools that find a source-document type on a file in `wiki/notes/`, or a zettel type on a file in `sources/`, SHOULD surface it as an error.

### 6.1 Source-document types (used in `sources/`)

| `type` | Description |
|---|---|
| `article` | An external article (web, magazine, blog). The body is the article text, cleaned of nav cruft and ads. |
| `book` | A book or book chapter. For long books, one source document per chapter is the typical pattern. |
| `quote` | A notable quotation extracted from a source. The body is the quoted passage as a Markdown blockquote. Often very short. |
| `transcript` | A verbatim transcript of a meeting, call, interview, or recorded talk. The body is the transcript text. |

More source-document types can be added (paper, podcast, video, webpage, email) as the user's workflow needs them. New types require an update to this spec.

### 6.2 Zettel types

| `type` | Description |
|---|---|
| `note` | Generic knowledge note. Default fallback when no other type fits. Body is a short essay or structured explainer. |
| `definition` | A short, precise explanation of one term. One or two paragraphs of prose plus an optional `## Example` section. |
| `procedure` | Step-by-step instructions for accomplishing a concrete task. Numbered list is the default. |
| `wiki-article` | Short, focused how-to describing one setting, tweak, or trick. Two to ten lines. |
| `cheatsheet` | Condensed reference for commands, shortcuts, or keybindings. Bullets or tables. |
| `snippet` | A standalone code sample with minimal commentary. Requires `language`. |
| `course` | Running notes from a course, book, or tutorial (the user's own notes, not the course material itself). Often long. |
| `ai-prompt` | Reusable prompt for an LLM. Body wraps the prompt in a triple-backtick fence. |

### 6.3 When to use which: utility vs. concept zettels

**Source-document types** are used by the capture step. They never describe content the user or the LLM wrote; they hold external material.

**Zettel types** divide into two practical clusters that map to the utility / concept distinction:

- **Concept zettels** typically have `type: note` or `definition`. They are produced by ingest, carry `concept-type`, `assent`, `lifecycle`, and claims, and link into MOCs. They turn source material into thought-material.
- **Utility zettels** typically have `type: procedure`, `wiki-article`, `cheatsheet`, `snippet`, `course`, or `ai-prompt` - practical forms kept for use, not for interrogation. They have NO `concept-type`, NO `assent`, NO `lifecycle`. Any of them MAY become a concept zettel by gaining the concept dimensions when its central idea turns out to be worth interrogating.

The vocabulary is deliberately knowledge-only. Personal-life and work-tracking forms (recipes, budgets, projects, meeting minutes, trackers) belong to the owner's separate manual vault, not to Klyreon; the human carries anything across by hand.

When in doubt, `note` is the default for knowledge content.

## 7. Concept zettel fields

When a zettel participates in Klyreon's operations (ingest, query, lint, rework, deliver), it carries additional fields beyond `type`. Three are closed-enumeration **concept dimensions** (sections 7.1-7.4), two are structured fields that carry the unit of cross-update and the unit of epistemic annotation (sections 7.5-7.6), and one pair is the review-tracking flag (section 7.7) which technically applies to every zettel but is documented here for locality.

The concept dimensions are what make a zettel a **concept zettel**. Zettels without them are utility zettels. Source documents NEVER have them.

### 7.1 `concept-type`: what epistemic shape is this?

The shape of the claim. Closed enumeration; authors do not invent new values without updating this spec.

| Value | Use when... |
|---|---|
| `thesis` | The zettel states a stand-alone claim you are making. |
| `argument` | The zettel traces a chain of reasoning supporting (or attacking) a thesis. |
| `aporia` | The zettel documents a known unresolved disagreement between sources or with yourself. |
| `question` | The zettel opens an inquiry. The body is a question, not an answer. |
| `example` | The zettel records a concrete case that exemplifies a more general claim. |
| `observation` | The zettel records a raw factual claim that has no thesis attached yet. |

`concept-type` is a compound field name, not a namespaced prefix. It is named that way to distinguish it from the legacy `type` field, which already carries a different meaning (the form: article, note, procedure, etc.). Both meanings need to coexist on the same file.

The two fields are orthogonal. Examples:

- `type: note, concept-type: thesis` — a knowledge zettel that states a thesis the vault is committing to.
- `type: note, concept-type: argument` — a knowledge zettel that argues for or against a thesis.
- `type: snippet` (no `concept-type`) — a snippet is a utility zettel; it has no epistemic role.

### 7.2 `assent`: do I endorse it?

The Stoic epistemic state. Closed enumeration.

| Value | Meaning |
|---|---|
| `accepted` | You stand behind it. Used by query and delivery as high-confidence material. |
| `tentative` | Provisional. Not yet committed. The default for new concept zettels (the Stoic-safe default: do not assent quickly). |
| `rejected` | You explicitly do not endorse it. The zettel is kept as a record of what you considered and decided against. Rejected zettels are not deleted. |
| `unknown` | You have not made up your mind. Lint surfaces these as candidates for review. |

Under autonomous operation the system applies assent on the owner's behalf, and transitions are rule-driven: a new concept zettel starts `tentative`; corroboration by independent accepted material is the path to `accepted`; an open `disagreement` doubt holds it at `tentative` or `unknown`; `rejected` records a claim refuted by accepted material or dismissed by the owner. Exact thresholds belong to the operational design. A human decision always overrides the rules, in either direction.

Defaulting to `tentative` keeps the wiki honest: commitment costs explicit corroboration rather than being free.

### 7.3 `lifecycle`: how mature is the form?

The commonplacing distillation state. Closed enumeration.

| Value | Meaning |
|---|---|
| `fleeting` | Quick capture. Raw. Survives only if it earns survival in a maintenance pass. |
| `literature` | Distilled per-source. Structured. Cited from one source, rendered in the vault's voice. |
| `evergreen` | Generalized across sources. Can stand alone without the source open in the next tab. |

Promotion and pruning are rule-driven maintenance operations and MAY run automatically; a human decision always overrides. A `fleeting` zettel that has earned links or corroboration over a maintenance window is a candidate for `literature`. A `literature` zettel cited by multiple sources and rewritten for general use is a candidate for `evergreen`.

The inverse also holds: a `fleeting` zettel still orphaned and uncorroborated at the end of the window is a pruning candidate. Pruning deletes the file and cleans inbound references; git history is the archive. Two exemptions: `assent: rejected` zettels (the record of what was considered and refused) and zettels carrying a non-empty `delivered-as` (deleting one breaks the provenance of work that already shipped). Exact windows and thresholds belong to the operational design.

### 7.4 Why the three dimensions are orthogonal

Each axis answers a different question. Same `concept-type` with different combinations of `assent` and `lifecycle` mean very different things.

| `concept-type` | `assent` | `lifecycle` | What this combination means |
|---|---|---|---|
| `thesis` | `accepted` | `evergreen` | A polished, endorsed, standalone claim. The wiki's load-bearing material. |
| `thesis` | `tentative` | `fleeting` | A half-baked draft you are still thinking through. |
| `thesis` | `rejected` | `literature` | You wrote it up properly, then the evidence turned against it. Kept as a record of evolution. |
| `question` | `unknown` | `fleeting` | An open question you just jotted down. |
| `argument` | `tentative` | `literature` | A structured argument you have not yet fully endorsed. |
| `aporia` | `unknown` | `evergreen` | A well-formed, durably-recorded open disagreement. |

What each dimension enables:

- **`concept-type`** is for **structure**: tools treat arguments differently from observations during ingest, dedup, and lint.
- **`assent`** is for **trust**: query results weight `accepted` zettels higher; lint hunts for stale `tentative` zettels; delivery cites `accepted` claims by default.
- **`lifecycle`** is for **maturation**: rework promotes zettels through stages.

A concept zettel's epistemic shape, your commitment to it, and its level of distillation are three separate facts that move on three separate clocks. Collapsing them would discard information the system uses at every operation.

### 7.5 Claims: structured atomic assertions

A concept zettel's body is prose. Prose is long, sparse, and expensive to compare against the rest of the wiki. The `claims` field is the structured distillate: one to three short assertions that the zettel is committing to, written in the same voice as the body but small enough that every claim in the wiki can fit in a single LLM context window for cross-comparison.

**Schema.**

```yaml
claims:
  - id: c1
    statement: Circuit breakers protect callers from cascading failures, not callees.
  - id: c2
    statement: Open/half-open/closed is the minimum viable state machine; anything simpler misclassifies.
```

Each entry has:

- **`id`**: a short local identifier unique within the zettel. The convention is `c1`, `c2`, `c3`. Claim IDs are not globally unique; they are referenced by `doubts` within the same zettel. They never change after creation (doubts and cross-zettel tools depend on stability).
- **`statement`**: a one-sentence assertion in plain language. No hedging, no citations, no multi-clause arguments. If a statement wants a "but" or a "however", split it into two claims or move the nuance into a doubt.

**Why claims are structured.**

The original impulse in Klyreon was to treat each zettel as an atomic idea and do cross-update at the prose level: when a new zettel lands, the tool walks every existing note and decides whether the new material touches it. This is retrieval-at-write-time, and it has the same recall problems that led Klyreon to reject RAG-style retrieval in the first place. At ~500 notes, prose-level top-k retrieval silently misses most of the cross-updates it should propose.

Structured claims cut the unit size by a factor of ten. At 2000 notes with two claims each and ~20 tokens per claim, the entire claim set fits in ~80k tokens: comfortably within a long-context window. Cross-update runs as a single-pass comparison against the full claim set, not as retrieval. The wiki compounds at the claim layer, while the prose body remains the place where nuance lives. This single-pass comparison is also Klyreon's contradiction detector: a new claim that conflicts with an existing one is recorded - a `disagreement` doubt on the affected claims, a `contradicts` link, or an aporia zettel - instead of silently coexisting with it.

**When to write claims.** A concept zettel with `concept-type: thesis`, `argument`, or `observation` MUST carry at least one claim: claims are the substrate of contradiction detection, and an assertion-bearing zettel without claims is invisible to it. `question` zettels usually do not carry claims (the body is a question, not an assertion).

`aporia` zettels carry NO claims of their own. They reference the disagreeing claims instead: a `contradicts` link to each side, plus a scope-level `disagreement` doubt (`claim: null`) whose `target` names the specific foreign claim (section 7.6). Restating the two claims inside the aporia would put copies of them into the claim set, and the claim set is what the contradiction detector and the dedup pass read: the detector would re-fire on its own record of a conflict it already recorded, and dedup would see phantom near-duplicates. The zettel that documents a resolved conflict must not feed the detector that found it.

**Who writes claims.** The ingest tool extracts claims at draft time, as part of the Socratic interrogation. Later review (human or automated) may add, edit, or remove claims; the `id` values of surviving claims are preserved to keep doubt references stable.

### 7.6 Doubts: Pyrrhonian annotations

The Skeptical tradition catalogues five modes in which an assertion can be honestly doubted. The `doubts` field records these modes as annotations on specific claims (or on the whole zettel), written while the LLM drafts and refined during any later review, human or automated.

**Schema.**

```yaml
doubts:
  - mode: context-relative
    claim: c1
    rationale: Assumes the caller can degrade gracefully. Synchronous user-facing paths cannot, so the protection applies only to batch and async contexts.
  - mode: regress
    claim: c2
    rationale: "Minimum viable" depends on what failure mode you tolerate. A system that accepts silent data loss can get by with two states.
  - mode: disagreement
    claim: c1
    target:
      to: wiki/notes/20260220221500.md
      claim: c1
    rationale: That claim reaches the opposite conclusion. Both cannot hold; theirs assumes a synchronous caller.
  - mode: assumption
    claim: null
    rationale: The whole zettel assumes a distributed microservice context. It does not apply to in-process libraries.
```

Each entry has:

- **`mode`**: one of the five Pyrrhonian modes: `disagreement`, `regress`, `context-relative`, `assumption`, `circular`. Closed enumeration. Authors do not invent new modes without updating this spec.
- **`claim`**: the local `id` of the claim the doubt attaches to, or `null` if the doubt is scope-level (applies to the whole zettel: a frame assumption, a context the zettel fails to state, a disagreement with the zettel's premise rather than with any individual claim).
- **`target`**: OPTIONAL. The foreign claim this doubt is raised against, as an object with `to` (root-relative path to the target zettel) and `claim` (the local `id` of the claim inside that zettel, or `null` for a zettel-level target). Required on `mode: disagreement` when the disagreement is with material elsewhere in the wiki; omitted on every other mode unless a foreign claim is genuinely the reason for the doubt. This is the only place a claim outside the current zettel may be named: claim `id` values are local, and `target` is what makes them addressable.
- **`rationale`**: one or two sentences explaining why the doubt applies. If the rationale needs more than two sentences, it has earned its own zettel; replace the long rationale with a link there.

**The five modes.**

| Mode | Use when... |
|---|---|
| `disagreement` | Another claim (in this zettel or elsewhere) reaches the opposite conclusion. Often paired with a `contradicts` link. |
| `regress` | The claim rests on a premise that itself needs justification. The chain has not been followed to a foundation. |
| `context-relative` | The claim is true only under a context the zettel does not fully state, or stops being true outside that context. |
| `assumption` | An unstated premise is doing load-bearing work. Surface it. |
| `circular` | The claim smuggles its conclusion into its premises. |

**What doubts enable.**

- **Precise lint.** Lint can query for structural conditions the prose body cannot express. "Find every claim whose zettel has `assent: accepted` and that carries a doubt with `mode: assumption`" returns the claims you endorsed despite an unarticulated premise: exactly the claims worth another pass of thinking.
- **Structural aporia.** If claim `c1` in zettel A carries a `mode: disagreement` doubt whose `target` is claim `c1` in zettel B, and the reverse also holds, the pair is an aporia automatically. The `concept-type: aporia` label becomes optional: aporia can be derived from the doubts graph. This derivation is why `target` exists - without an addressable foreign claim, a recorded contradiction collapses to zettel granularity and cannot be mechanically re-checked after either side is edited.
- **Honest delivery.** When delivery cites a claim in a deliverable, the delivery tool can refuse to omit that claim's doubts unless the owner explicitly waives them, claim by claim.

**Who writes doubts.** LLM-authored doubts on unprocessed drafts are valuable and encouraged. An LLM that notices its own uncertainty and records it is enacting exactly the discipline the Skeptics were teaching. Later review (human or automated) may add, edit, or remove doubts.

### 7.7 Review tracking

`processed` and `reviewed` (section 5.2) answer one question: has a human looked at this zettel in its current state? They are opportunistic markers, not gates. No operation waits for, requires, or is blocked by human review; the system ingests, cross-updates, promotes, and prunes indefinitely on its own. When a human does review, the record makes that visible.

- `processed: false` on every tool-drafted zettel at creation, and reset to `false` when an automated operation changes the zettel's **content**: claims or doubts added, edited, or removed. After a reset, the stored `reviewed` timestamp stays but is older than `updated`: the review is stale.
- Rule-driven `assent` and `lifecycle` transitions (sections 7.2, 7.3) do NOT reset the flag, and neither do trivial changes (adding an outbound link, retagging). Those transitions are the system applying rules the owner already set, not new material a human has never seen. Resetting on them would drive `processed` to permanently `false` under autonomous operation, which costs a write on every maintenance pass and leaves the flag's one consumer unable to discriminate. The trade accepted here: a zettel can move `tentative` to `accepted` while still reading `processed: true`, so the flag attests that a human saw the zettel's claims and doubts, not that they endorsed its current assent.
- `processed: true` plus `reviewed: <now>` when a human accepts the zettel in a review session.
- User-authored zettels may omit both fields entirely.

Query and delivery MAY weight `processed: true` zettels higher as a tie-break between candidates with equivalent claim matches. Nothing else reads the flag. A zettel is never excluded because it is unprocessed. (Assent answers a different question - "does the vault endorse this?" - and moves on its own clock; see section 7.2.)

## 8. Relations vocabulary

`links` carries directed relations between zettels. The vocabulary is closed and capped at ten entries. Authors do not invent new relations.

| Relation | Meaning | Inverse | Transitive |
|---|---|---|---|
| `supports` | A provides evidence for B | (asymmetric) | no |
| `contradicts` | A and B are inconsistent | symmetric | no |
| `exemplifies` | A is a concrete case of B | (asymmetric) | no |
| `supersedes` | A replaces B; B is expected to carry `assent: rejected` | (asymmetric) | no |
| `defines` | A is the canonical definition of B | (asymmetric) | no |
| `analogous-to` | A and B share structure across domains | symmetric | no |
| `causes` | A causes B | (asymmetric) | no |
| `requires` | A is a prerequisite for B | (asymmetric) | yes |
| `broader-than` | A is the parent concept of B | `narrower-than` | yes |
| `narrower-than` | A is a child concept of B | `broader-than` | yes |

The cap is intentional. A previous iteration grew the vocabulary to seventeen relation types and produced decision fatigue with no proportional gain. If you genuinely need an eleventh relation, replace one. Do not add.

`supersedes` records the third resolution shape of contradiction detection. A detected conflict resolves into exactly one of: **aporia** (neither side wins - `disagreement` doubts on both sides, and optionally an `aporia` zettel), **refine** (the new claim qualifies the old one - `narrower-than`), or **supersede** (the new claim replaces the old one - `supersedes`, and the superseded zettel moves to `assent: rejected`). Without the third relation the shape is only inferable from a `contradicts` link plus an assent state, which is ambiguous: `contradicts` is symmetric and carries no direction of replacement, and `rejected` does not say why. Lint's "claims superseded by newer sources" check queries this relation.

It replaced `questions` ("A raises doubt about B"), which a `mode: disagreement` doubt with a `target` (section 7.6) now expresses at claim precision rather than zettel precision.

**Transitivity.** The three relations marked transitive MUST NOT form a cycle: if A `broader-than` B and B `broader-than` C, then C MUST NOT be `broader-than` A, directly or through any chain. A cycle in a transitive relation silently breaks every hierarchy walk that depends on it. Transitive closures are computed at query time, never stored. Tools that detect a cycle SHOULD surface it as an error.

### 8.1 Link entry shape

Each entry in `links` is a YAML object with two required keys:

```yaml
links:
  - rel: supports
    to: wiki/notes/20260301093210.md
  - rel: contradicts
    to: wiki/notes/20260220221500.md
```

`rel` is one of the ten relations above. `to` is a root-relative path to the target zettel (section 10). Both fields are required. Tools that find a malformed entry SHOULD surface it as an error.

`links` targets are zettels, never source documents. Cross-references from a zettel to a source document use `sources`, not `links`.

## 9. Tags

`tags` is a list of free domain descriptors: kebab-case, the owner's vocabulary. They answer "what is this about?", nothing more.

```yaml
tags:
  - resilience
  - fault-tolerance
  - circuit-breaker
```

Hierarchical tags use `/`: `lang/rust`, `client/412-acme-corp`, `country/cz-czech-republic`. Levels nest from broad to narrow. Tags apply to both species.

There are NO tag namespaces. Earlier revisions encoded philosophical dimensions as colon-prefixed namespace tags (`topos:*`, `kind:*`, `sphere:*`, `doubt:*`, `output:*`). Every dimension that earns its keep has a dedicated frontmatter field instead (`concept-type`, `assent`, `lifecycle`, `claims`, `doubts`, `delivered-as`); the rest were retired as classification burden with no consuming operation. Lint SHOULD flag any colon-prefixed tag as legacy.

## 10. Internal paths and the system configuration file

All paths inside any file (`sources`, `links.to`, `mocs`) are **relative to a root**. The root is defined externally in a YAML configuration file at:

```text
~/.config/klyreon/config.yaml
```

(Respecting `$XDG_CONFIG_HOME` when set: `$XDG_CONFIG_HOME/klyreon/config.yaml`.)

The configuration file's minimum content:

```yaml
# Path to the Klyreon root.
# Every relative path inside any zettel or source document resolves under this directory.
root: /Users/bob/Documents/klyreon
```

When a tool (ingest, query, lint) reads a file, it loads `~/.config/klyreon/config.yaml` first to discover the root. It then resolves every path field by joining the root and the relative path.

Example. With `root: /Users/bob/Documents/klyreon` and a zettel containing:

```yaml
sources:
  - sources/archive/2026-04/article-resilience-patterns.md
links:
  - rel: supports
    to: wiki/notes/20260301093210.md
mocs:
  - wiki/mocs/architecture.md
```

The resolved absolute paths are:

- `/Users/bob/Documents/klyreon/sources/archive/2026-04/article-resilience-patterns.md`
- `/Users/bob/Documents/klyreon/wiki/notes/20260301093210.md`
- `/Users/bob/Documents/klyreon/wiki/mocs/architecture.md`

### 10.1 Why root-relative

Three reasons.

1. **Relocation safety.** Move the wiki to a different directory and update the config. Nothing inside any file changes.
2. **Test environment isolation.** Different test environments can point at different roots without rewriting fixtures.
3. **Explicit interpretation.** Every path in every field is interpretable on its own without "implicit `notes/` prefix" or "implicit `mocs/` prefix" rules. A tool reading a path does not need to know which field it came from to know how to resolve it.

### 10.2 What the root must contain

The root is a directory that contains at minimum:

```text
<root>/
├── sources/
│   ├── YYYY-MM/        # unprocessed source documents
│   └── archive/
│       └── YYYY-MM/    # source documents whose derived zettels have been approved
└── wiki/
    ├── notes/          # zettels (concept and utility)
    ├── mocs/           # maps of content (the loci "rooms")
    └── trails/         # session logs
```

Of the other directories that may appear under `wiki/`, only `assets/` is used by this spec (image downloads, section 11.2). Anything else (`arrangements/`, wiki-level files such as `index.md`, `log.md`, `lint-report.md`) belongs to Klyreon's operational design, specified separately; it is an open item for the requirements phase.

### 10.3 External links

External URLs (web pages, repositories, dashboards) use plain Markdown links inside the body:

```markdown
See [the original paper](https://example.com/paper.pdf) for the experiment.
```

External links never go in `links`. The `links` field is for intra-wiki zettel-to-zettel relations only. The original source URL of an article belongs in the source document's `article-url` field, not on the zettels derived from it.

### 10.4 Configuration file resolution rules

- Tools resolve `~` to the user's home directory using the standard expansion (e.g. `/Users/bob`).
- The `root` value MUST be an absolute path. Relative paths in the config file are an error.
- The `root` directory MUST exist when a tool runs. Tools that find a missing root SHOULD fail loudly rather than silently create directories.
- A path that escapes the root via `..` segments is an error. Tools MUST reject paths containing `..`.

## 11. Body shape

The body is free-form Markdown. The shape depends on the species, the `type`, and (for concept zettels) the `concept-type`.

### 11.1 H1 rule (both species)

Exactly one H1 per file. The H1 text matches the `title` frontmatter field exactly. No decorative prefixes, no trailing dates, no emoji. The H1 should make sense out of context.

### 11.2 Source document body

The body of a source document is the source's content, cleaned but not paraphrased. For an `article`, it is the article text. For a `book` chapter, it is the chapter. For a `quote`, it is a Markdown blockquote with the quoted passage. For a `transcript`, it is the transcript text.

Cleaning is allowed:

- Remove navigation cruft, ads, footers, cookie banners (typical when capturing web content).
- Convert HTML to clean Markdown (lists, headings, code blocks).
- Download referenced images to `wiki/assets/YYYY-MM/` and update embeds to relative paths.

Paraphrasing is NOT allowed at the source-document layer. The whole point of a source document is to preserve what the source actually said. Interpretation goes in derived concept zettels.

### 11.3 Concept zettel body, Socratic shape (when `concept-type: thesis` or `argument`)

Concept zettels with `concept-type: thesis` or `concept-type: argument` strongly prefer the **Socratic shape**, named for the discipline of probing claims that Socrates made his method:

```markdown
# Title that mirrors the H1

## Claim
One or two sentences, paraphrased from the source into the vault's voice.

## Assumptions
What must be true for this to work.

## Evidence
Main support, plus the strongest objection.

## Implications
What this changes about how you act, decide, or design.
```

Other `concept-type` values use lighter shapes:

- `observation` and `example`: usually one or two paragraphs of plain text.
- `question`: the body is the question, optionally followed by what you have already considered.
- `aporia`: the body names the disagreement and links to the contradicting zettels via `links`.

### 11.4 Utility zettel body, type-driven shapes

Utility zettels (no `concept-type`) use type-driven body conventions:

- `definition`: one or two paragraphs of prose plus optional `## Example`.
- `procedure`: a numbered list, possibly with sub-steps.
- `wiki-article`, `cheatsheet`: bullets or short prose, no sections.
- `snippet`: one or two lines of explanation followed by a fenced code block.
- `course`: running notes, often long; chronological sections.
- `ai-prompt`: the prompt wrapped in a triple-backtick fence.

These conventions are recommendations, not enforced schemas. The system does not parse them.

### 11.5 Voice and paraphrase

The wiki has a coherent voice, and that voice is not the source's. The ingest tool drafts every concept zettel in a paraphrased, interpreted form: it reads the source, extracts the idea, and renders the idea in the vault's voice configuration (tone, register, preferred vocabulary, second person or third - where this configuration lives is part of the operational design). Quoted source text does not compound the way paraphrased text does, so verbatim copy from a source is avoided.

The labor split follows Karpathy's LLM Wiki pattern: the human sources, questions, and occasionally reviews; the LLM writes and maintains. The paraphrase discipline is a constraint the LLM applies to its own drafting, not a cognitive ritual the human performs. What makes the output valuable is that the ideas have been interrogated (the Socratic probe, the Skeptical doubt modes, Stoic assent), not that a human hand typed the sentences. The vault's voice is the LLM's rendering under the owner's voice configuration.

Direct quotation in a concept zettel is permitted only when the exact wording matters: a definition being critiqued, a claim quoted verbatim to argue against. Quotes use Markdown blockquotes (`> ...`) and SHOULD be followed by the zettel's interpretation or commentary.

Source documents are the opposite: their body IS the source's words, and neither the user nor the LLM edits them beyond cleaning.

## 12. Complete examples

### 12.1 Source document: a captured article

A `type: article` source document with the article text as the body:

````markdown
---
id: article-resilience-patterns
title: "Patterns for resilient distributed systems"
created: 2026-04-11T14:50:00+02:00
type: article
tags:
  - resilience
  - distributed-systems
article-author: Marc Brooker
article-publication: brooker.co.za
article-url: https://example.com/resilience-patterns
---

# Patterns for resilient distributed systems

Distributed systems fail in characteristic ways. The patterns that survive
production are the ones that assume failure is the default and design every
call path to degrade gracefully.

## Circuit breakers

A circuit breaker monitors a downstream and trips open when failures cross a
threshold. While open, calls fail fast instead of waiting for timeouts. After
a cooldown the breaker enters a half-open state and tries one call to see if
the downstream has recovered.

The Hystrix library popularized this pattern at Netflix. Their published
data showed a p99 latency drop from 4 seconds to 200ms on a flaky payment
provider. The trade-off is a measurable false-open rate during the recovery
window.

## Bulkheads

[... rest of the article body ...]
````

This file is the raw material. It has no `concept-type`, no `assent`, no `lifecycle`, no `links`, no `mocs`. It lives in `sources/2026-04/article-resilience-patterns.md` and moves to `sources/archive/2026-04/article-resilience-patterns.md` after its derived concept zettels are approved.

### 12.2 Concept zettel derived from the article

A concept zettel produced by ingest of the article above. Ingest applies the Socratic probe and the Skeptical doubt modes while drafting; the note lands `processed: false` (a human may review it opportunistically; nothing waits for that).

````markdown
---
id: "20260411145300"
title: Circuit breakers trade tail latency for systemic recovery
created: 2026-04-11T14:53:00+02:00
updated: 2026-04-11T15:02:14+02:00
type: note
concept-type: thesis
assent: tentative
lifecycle: literature
processed: false
claims:
  - id: c1
    statement: A circuit breaker reduces latency tail on a distributed call chain by failing fast on a known-broken downstream.
  - id: c2
    statement: The cost of the pattern is a measurable false-open rate during the recovery window.
doubts:
  - mode: context-relative
    claim: c1
    rationale: Only holds when failing fast is acceptable to the caller. Synchronous user-facing requests cannot degrade gracefully, and in that context the pattern moves the problem from latency to error rate.
  - mode: assumption
    claim: c1
    rationale: Assumes the downstream's failures are correlated in time (a half-second blip, not random per-call jitter). If failures are uncorrelated, the open state opens on noise.
sources:
  - sources/archive/2026-04/article-resilience-patterns.md
links:
  - rel: supports
    to: wiki/notes/20260301093210.md
  - rel: contradicts
    to: wiki/notes/20260220221500.md
mocs:
  - wiki/mocs/architecture.md
tags:
  - resilience
  - circuit-breaker
---

# Circuit breakers trade tail latency for systemic recovery

## Claim

A circuit breaker reduces the latency tail of a distributed call chain by failing fast on a known-broken downstream, at the cost of some legitimate calls during the open period.

## Assumptions

- The downstream's failures are correlated in time (a half-second blip, not random per-call jitter).
- Failing fast is preferable to retrying for the workload in question.

## Evidence

The Resilience Patterns article (`sources/archive/2026-04/article-resilience-patterns.md`) cites Hystrix data showing p99 latency drop from 4 seconds to 200ms on a flaky downstream. The strongest objection is in `wiki/notes/20260220221500.md`: in workloads where every call must be served, a circuit breaker just moves the problem from latency to error rate.

## Implications

For the booking flow we are designing, this is a strong fit. For the payments flow, it is a worse fit.
````

This concept zettel is the LLM's interpretation of the source under the vault's voice conventions. It paraphrases the article's claim, extracts two structured claims for cross-update, records the doubts ingest noticed, and links to other zettels in the wiki. It cites the source document via `sources` so the original is one click away. It stays `processed: false` unless a human reviews it; nothing depends on that.

### 12.3 Utility zettel: a snippet

A `type: snippet` utility zettel with no `concept-type`, `assent`, `lifecycle`, `claims`, or `doubts`. Authored directly by the user, so `processed` is absent:

````markdown
---
id: "20260408180230"
title: Find files by content with ripgrep and edit them
created: 2026-04-08T18:02:30+02:00
type: snippet
language: bash
tags:
  - cli
  - search
---

# Find files by content with ripgrep and edit them

List only the files whose content matches, then open them in the editor.

```bash
rg -l "pattern" | xargs -o nvim
```
````

This is a utility zettel. It does not participate in Klyreon's operations. It lives in the wiki because it is useful next to the knowledge work.

### 12.4 Source document: a quote, plus a derived observation concept zettel

A `type: quote` source document, very short:

````markdown
---
id: quote-aurelius-confine-to-present
title: "Marcus Aurelius: confine yourself to the present"
created: 2026-03-09T09:30:00+02:00
type: quote
tags:
  - stoicism
quote-author: Marcus Aurelius
quote-source: "Meditations, Book VII"
---

# Marcus Aurelius: confine yourself to the present

> Confine yourself to the present.
````

And the concept zettel the user reviewed and endorsed:

````markdown
---
id: "20260309093045"
title: The present is the only frame in which the will is active
created: 2026-03-09T09:30:45+02:00
updated: 2026-03-09T10:15:00+02:00
type: note
concept-type: observation
assent: accepted
lifecycle: evergreen
processed: true
reviewed: 2026-03-09T10:15:00+02:00
claims:
  - id: c1
    statement: The present is the only temporal frame in which the will has anything to act on; past and future are categorically out of the sphere of control.
sources:
  - sources/archive/2026-03/quote-aurelius-confine-to-present.md
mocs:
  - wiki/mocs/self.md
tags:
  - stoicism
  - presence
---

# The present is the only frame in which the will is active

The discipline that Marcus Aurelius captures with "confine yourself to the present" is the same one Epictetus puts as "some things are up to us, and some are not." The present is the only temporal frame in which the will actually has anything to act on. Past and future are categorically out of the sphere of control. The instruction is a sphere-of-control reminder framed as a temporal one.
````

The quote lives once in `sources/`. The interpretation lives in a concept zettel that links to it. This one has been reviewed: `processed: true`, `reviewed` stamped, `assent: accepted`, and `lifecycle: evergreen` after the user stood behind it during a review session. It carries no doubts because the review did not surface any.

## 13. Authoring rules of thumb

- One zettel, one idea. If a zettel starts sprouting unrelated sub-sections, split it.
- One source document, one external item. Long books are typically split into one source document per chapter.
- The H1 is the elevator pitch. Rewrite it until it stands alone in an index entry.
- For concept zettels: default `assent` to `tentative`, `lifecycle` to `fleeting`, and `processed` to `false`. Promotion is a separate maintenance act - rule-driven and possibly automatic - never a side effect of writing.
- Assertion-bearing concept zettels (`thesis`, `argument`, `observation`) MUST carry one to three `claims` entries, each a one-sentence assertion with a stable local `id`. Claims are the unit of cross-update and contradiction detection; bodies are the unit of reading.
- Doubts are attached to specific claims via the claim's `id`, or to the whole zettel via `claim: null`. A doubt raised against material elsewhere in the wiki names it via `target`; that is the only way to address a claim outside the current zettel. Authoring tools SHOULD record doubts the moment they are noticed, including on unprocessed drafts.
- `aporia` zettels carry no claims of their own. They point at both sides via `contradicts` links and a `disagreement` doubt with a `target`.
- Every concept zettel SHOULD link into at least one MOC via `mocs`. Orphans get caught at lint.
- Utility zettels (procedure, wiki-article, cheatsheet, snippet, course, ai-prompt) have no `concept-type`, `assent`, `lifecycle`, `claims`, or `doubts`. They are not lesser; they are just not philosophical material.
- Never invent a new `type` value, a new `concept-type` value, a new doubt `mode`, a new relation, or a new tag namespace without updating this spec first.
- Every relative path MUST resolve under the configured root. Tools that find a path that does not resolve SHOULD surface it as an error, not silently coerce it.
- Concept zettel bodies are written in the vault's voice, as defined by the vault's voice configuration. The LLM paraphrases source material; it does not copy it. Source document bodies are the source's content, cleaned but not paraphrased.
- Quote the whole frontmatter value when it contains a `:` so YAML does not misparse it.
- Any tool that generates files MUST set `publish: false` if it sets `publish` at all. Only the human owner flips it to `true`.
- Any tool that generates a zettel, or changes an existing zettel's claims or doubts, MUST set `processed: false`. Rule-driven `assent` and `lifecycle` transitions MUST NOT. Only a human review session flips the flag to `true`.

## 14. Compatibility notes

- **Obsidian.** All standard frontmatter fields (`title`, `tags`, `created`) work in Obsidian's UI exactly as you would expect. The compound field name `concept-type` is visible in the metadata pane but is not surfaced in any special UI.
- **Dataview.** Dataview can query any frontmatter field by name. Queries on `concept-type` need bracket syntax in some expressions: `WHERE row["concept-type"] = "thesis"`. Queries on unprefixed fields (`assent`, `lifecycle`, `type`) work with the natural dot syntax.
- **Git.** Every file is plain text. Diffing, blame, and history work normally.
- **Plain Markdown viewers.** All files render as valid Markdown in any viewer. The YAML frontmatter shows as a code block in viewers that do not strip it.
- **Cross-tool interoperability.** Non-system fields (e.g. `aliases`, `cssclasses`, custom dataview keys) are tolerated and ignored by Klyreon. Tools that rewrite a file MUST preserve unknown fields rather than dropping them.
