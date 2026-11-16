# Tiromex Zettel Format Specification

This document defines the file format of **tiromex** notes: the concept notes that bim keeps in one folder of the zettelkasten. Any tool that reads, writes, or validates a tiromex note MUST follow this spec. `bim tx validate` checks it mechanically (section 12).

A tiromex note is a bim note. It uses bim's frontmatter, bim's key order, and bim's backmatter. The tx layer adds closed vocabularies and rules on top. It does not add a second file model.

This spec is the revision of the Klyreon format specification (`docs/reference/klyreon/zettel-format-specification.md`). The main changes:

- `date`, not `created`, carries the creation time.
- Frontmatter keys follow bim's order (section 5.1).
- Relations, the parent index, and sources live in the backmatter, not in frontmatter lists (section 8).
- Index notes replace Maps of Content (section 3.3).
- Sources are `mirror:<root>/<path>` values. There is no source-document species in the vault (section 9).
- Run journals are notes with `type: tx-run` (section 3.4).

## 1. Philosophical foundation

Tiromex is grounded in seven ancient knowledge-building disciplines. Each one shapes a part of the format. The disciplines describe how the writer thinks about the material, not who holds the pen. An LLM writes and maintains most notes. A human may review, but no operation waits for that.

| Lever | Implementation in this spec |
|---|---|
| **Socratic** interrogation | `claims` (section 7.4) and the body shape for `thesis` and `argument` notes (section 11.3). |
| **Aristotelian** typing | `type` (the form, section 6) and `concept-type` (the epistemic shape, section 7.1). |
| **Stoic** assent | `assent` (section 7.2). Rule-driven transitions; a human decision always overrides. |
| **Pyrrhonian Skeptical** modes of doubt | `doubts` (section 7.5), attached to claims or to the whole note. |
| **Method of loci** | Index notes (section 3.3) are the rooms. Every concept note links to one through `parent`. |
| **Commonplacing** | `lifecycle`: `fleeting`, `literature`, `evergreen` (section 7.3). |
| **Ciceronian** canons of rhetoric | `delivered-as` (section 5.3) records what a note has shaped. |

## 2. Note kinds

Every Markdown file in the tiromex folder is one of four kinds. The kind decides which rules apply.

| Kind | How it is recognized | Purpose |
|---|---|---|
| **concept** | the frontmatter has the key `concept-type` (any value) | one atomic idea, with the concept fields of section 7 |
| **index** | no `concept-type`, and `type: index` | a room that groups member notes (section 3.3) |
| **run** | no `concept-type`, and `type: tx-run` | the journal of one tx run (section 3.4) |
| **plain** | anything else | any other note an agent keeps in the folder |

The test runs in that order. A note with `concept-type` is a concept note whatever its `type` says.

Plain notes get only the base checks: the file parses, and `id`, `title`, `date` and `type` are present. They never feed the claim index.

## 3. File identity and location

### 3.1 The tiromex folder

Tiromex notes live in `<path_zettelkasten>/<tiromex_folder>/`. With bim's defaults that is `~/bim/notes/tiromex/`. The vault root is the parent of `path_zettelkasten`, so the folder is `notes/tiromex/` relative to the vault root.

- `tiromex_folder` is one plain folder name. It may not be empty, absolute, `.`, `..`, or hold more than one path part.
- The folder may not be a symlink, and it must resolve to exactly `<path_zettelkasten>/<tiromex_folder>`. tx can never be pointed at private notes elsewhere.
- tx reads every `*.md` file under the folder, recursively, in path order. A file whose resolved path leaves the folder (a symlink out) is skipped.

### 3.2 File names and ids

Every concept, index and run note is named `<id>.md`, where `id` is 14 digits:

```text
YYYYMMDDHHmmSS.md
```

- `YYYY` year, `MM` month, `DD` day, `HH` hour (24h), `mm` minute, `SS` second.
- The timestamp is the local wall-clock time of creation. `date` carries the offset and is the authority for real time.
- The `id` field equals the file stem. The id never changes. Renaming a file breaks every link to it.

Example: `notes/tiromex/20260411145300.md` was created on 11 April 2026 at 14:53:00 local time.

**Collision rule.** `bim tx new` takes `id` and `date` from the local clock. When the id is taken, it waits one second and builds the note again, up to five attempts. The file is reserved with an exclusive create, so two writers never share an id. `id` and `date` always agree.

### 3.3 Index notes

An index note is a room: it groups the notes that belong together.

- `type: index`, a 14-digit `id`, and the file name `<id>.md`, like every tx note.
- The title starts with `§ ` (section sign and one space), for example `§ Resilience`. The H1 matches it.
- The body holds at most one members block:

  ```markdown
  <!-- tx:members -->
  - [[notes/tiromex/20260411145300|Circuit breakers trade tail latency for systemic recovery]]
  <!-- /tx:members -->
  ```

  Either both markers are absent, or there is exactly one open marker followed later by exactly one close marker.
- A member note links to its index with a `parent` line in its backmatter:

  ```markdown
  - parent:: [[notes/tiromex/20260301090000|§ Resilience]]
  ```

Every concept note SHOULD have a `parent`. A concept note without one is an orphan, and `bim tx validate` reports it.

### 3.4 Run notes

A run note is the journal of one tx run: sources read, notes created, each conflict and the shape it resolved into, promotions, prune candidates.

- `type: tx-run`, a 14-digit `id`, and the file name `<id>.md`.
- The base fields, the tag rules, the H1 rule and the id rules apply.
- The body is free under its H1. There is no body-size limit and no members block.
- A run note carries no concept fields.

## 4. Overall layout

Every tiromex note has this layout:

```text
---
<YAML frontmatter>
---

# <H1 title>

<body>

---

<backmatter>
```

- The frontmatter is a YAML block at the very start of the file, between two `---` lines.
- The body opens with a single `# H1` whose text equals `title`.
- The backmatter is optional. It starts at the first line after the frontmatter that is exactly `---`. Each backmatter line has the form `- key:: value`.

**A tiromex body holds no `---` line of its own.** bim splits the note at the first `---` line after the frontmatter, so any such line ends the body and starts the backmatter. A horizontal rule in the body would turn the rest of the body into backmatter. A note that breaks this fails validation. Use a heading or a blank line instead of a rule.

**A concept or index note holds at least one body line under its H1.** A body that is only the H1 fails with `empty-body`. bim's formatter writes a second H1 into a note whose body is only an H1 followed by backmatter, so this rule keeps tx notes clear of that defect. `bim tx new` writes the H1 alone and no backmatter; add a body line before the first backmatter line.

## 5. Frontmatter

YAML. Keys are lowercase ASCII with dashes where needed. Quote a value when YAML needs it (an embedded colon, a leading special character). Booleans are `true` or `false`.

### 5.1 Key order

bim writes frontmatter keys in this order:

1. `id`
2. `title`
3. `date`
4. `tags`
5. `type`
6. `publish`
7. `processed`
8. every other key, in insertion order

Unknown keys survive a rewrite: the formatter writes all metadata. `bim format` may add default keys (`tags: []`, `publish: false`, `processed: false`) and may rewrite dates into the local zone.

### 5.2 Required fields (every kind)

| Field | Type | Description |
|---|---|---|
| `id` | 14 digits | Equals the file stem (section 3.2). Compared as text, so a bare YAML number is fine. Never changes. |
| `title` | string | Declarative title. MUST match the H1 exactly. For an index note it starts with `§ `. Quote it when it holds a colon. |
| `date` | ISO 8601 datetime | Creation time with offset, for example `2026-04-11T14:53:00+02:00`. The digits of `date` MUST equal `id`, either in the value's own offset or in the local zone. Never changes. |
| `type` | string | The form of the note. For a concept note: section 6. `index` for an index note, `tx-run` for a run note. |

A field that is missing or blank fails `required-field`.

### 5.3 Optional fields

| Field | Type | Description |
|---|---|---|
| `tags` | list of strings | Free domain tags (section 10). |
| `publish` | boolean | Owner-controlled. A tiromex note MUST NOT carry `publish: true`. Tools only ever write `false`. |
| `processed` | boolean | `false` on tool-drafted notes no human has reviewed. `true` after an opportunistic review. See section 7.6. |
| `updated` | ISO 8601 datetime | Last change. A tool that changes a note's frontmatter or body sets it. |
| `reviewed` | ISO 8601 datetime | Most recent human review. Absent until the first review. MUST NOT be older than `updated` (else the review is stale). |
| `delivered-as` | list of strings | Concept notes only. Ids of deliverables this note has shaped (`blog/resilient-architecture-2026-04`). A note with a non-empty `delivered-as` is never a prune candidate. |

Every `date`, `updated` and `reviewed` value is read as a YAML datetime, a YAML date (midnight of that day), or an ISO 8601 string. A naive value gets the local zone. A value that cannot be read makes the date rules skip that note.

### 5.4 Concept fields (concept notes only)

| Field | Type | Description |
|---|---|---|
| `concept-type` | enum | Required on a concept note; its presence makes the note a concept note. Section 7.1. |
| `assent` | enum | Optional. Section 7.2. `bim tx new` writes `tentative`. |
| `lifecycle` | enum | Optional. Section 7.3. `bim tx new` writes `fleeting`. |
| `claims` | list of objects | Structured assertions. Section 7.4. |
| `doubts` | list of objects | Pyrrhonian doubt annotations. Section 7.5. |

Index, run and plain notes carry none of these fields. A note that carries `concept-type` is a concept note by definition (section 2).

## 6. The `type` vocabulary of concept notes

`type` on a concept note is the form of the note. It is a closed list:

| `type` | Description |
|---|---|
| `note` | Generic knowledge note. The default. |
| `definition` | A short, precise explanation of one term. |
| `procedure` | Step-by-step instructions for one task. |
| `wiki-article` | A short how-to about one setting or trick. bim rewrites it to `note` on load, so `bim tx new` does not offer it. |
| `cheatsheet` | Condensed reference: commands, shortcuts, keybindings. |
| `snippet` | A standalone code sample with little commentary. |
| `course` | Running notes from a course, book, or tutorial. |
| `ai-prompt` | A reusable LLM prompt in a fenced block. |

A concept note with any other `type` fails `type-species`. Source-document types (`article`, `book`, `quote`, `transcript`) are gone: sources live outside the vault (section 9).

`type` and `concept-type` are orthogonal. `type: note` with `concept-type: thesis` is a knowledge note that states a thesis. A note without `concept-type` is not a concept note, whatever its `type`.

## 7. Concept fields

### 7.1 `concept-type`: what epistemic shape is this?

| Value | Use when... |
|---|---|
| `thesis` | The note states a stand-alone claim. |
| `argument` | The note traces a chain of reasoning for or against a thesis. |
| `aporia` | The note records a known unresolved disagreement. |
| `question` | The note opens an inquiry. The body is a question, not an answer. |
| `example` | The note records a concrete case of a more general claim. |
| `observation` | The note records a raw factual claim with no thesis attached yet. |

Closed list. Any other value, or a value that is not a string, fails `concept-type-enum`.

### 7.2 `assent`: does the vault endorse it?

| Value | Meaning |
|---|---|
| `accepted` | The vault stands behind it. Query and delivery treat it as high-confidence material. |
| `tentative` | Provisional. The default for new concept notes. |
| `rejected` | Explicitly not endorsed. Kept as a record, never deleted for this reason. |
| `unknown` | No decision yet. |

Closed list (`assent-enum`). Transitions are rule-driven: a new note starts `tentative`; corroboration by independent accepted material leads to `accepted`; an open `disagreement` doubt holds it at `tentative` or `unknown`; `rejected` records a claim refuted by accepted material or dismissed by the owner. A human decision always overrides.

### 7.3 `lifecycle`: how mature is the form?

| Value | Meaning |
|---|---|
| `fleeting` | Quick capture. Survives only if it earns survival. The default for new concept notes. |
| `literature` | Distilled from one source, in the vault's voice. |
| `evergreen` | Generalized across sources. Stands alone. |

Closed list (`lifecycle-enum`). Promotion is a rule-driven maintenance act. Pruning is report-only by default: maintenance lists candidates and deletes nothing until the owner sets `tx.pruning_enabled`. A prune candidate is a concept note with `lifecycle: fleeting`, assent not `rejected`, an empty `delivered-as`, no relation links in or out, and an anchor (`updated`, else `date`) older than `tx.prune_window_days` (default 365).

### 7.4 Claims

The body is prose. `claims` is its structured distillate: one to three short assertions, small enough that the whole claim set of the vault fits in one context window for cross-comparison. The claim set is the substrate of contradiction detection.

```yaml
claims:
  - id: c1
    statement: Circuit breakers protect callers from cascading failures, not callees.
  - id: c2
    statement: Open, half-open and closed is the minimum viable state machine.
```

Each entry is a mapping with:

- **`id`**: a local id, unique within the note. The convention is `c1`, `c2`, `c3`. It never changes, because doubts depend on it.
- **`statement`**: one plain sentence. No hedging, no citations. If it wants a "but", split it or move the nuance into a doubt.

Rules:

- `claims`, when present, is a list (`claims-shape`). Each entry has `id` and `statement` (`claim-shape`).
- A `thesis`, `argument` or `observation` note MUST carry at least one claim. A missing, null or empty `claims` fails `claims-required`.
- An `aporia` note carries NO claims of its own (`aporia-no-claims`). It points at both sides instead (section 7.5). Copies of the disputed claims in the aporia would feed the detector its own record of the conflict.
- A list holds at most three claims. On a `question` or `example` note an empty list is not allowed either: leave `claims` out, or give one to three (`claims-count`).

`bim tx new` with a claim-bearing concept type writes one starter claim, `c1`, whose statement is the title. `bim tx export-claims` prints every well-formed claim of every concept note, rejected notes included.

### 7.5 Doubts

The Skeptical tradition names five modes in which an assertion can be honestly doubted. `doubts` records them on specific claims or on the whole note.

```yaml
doubts:
  - mode: context-relative
    claim: c1
    rationale: Assumes the caller can degrade gracefully. Synchronous user-facing paths cannot.
  - mode: disagreement
    claim: c1
    target:
      to: notes/tiromex/20260220221500.md
      claim: c1
    rationale: That claim reaches the opposite conclusion. It assumes a synchronous caller.
  - mode: assumption
    claim: null
    rationale: The whole note assumes a distributed service context.
```

Each entry is a mapping with:

- **`mode`**: one of `disagreement`, `regress`, `context-relative`, `assumption`, `circular` (`doubt-mode-enum`).
- **`claim`**: the local `id` of a claim, or `null` for a doubt on the whole note.
- **`rationale`**: one or two sentences. A longer rationale has earned its own note.
- **`target`**: optional. The foreign claim the doubt is raised against: a mapping with `to` (the vault-relative path of the target note, **with** `.md`, for example `notes/tiromex/20260301101500.md`) and `claim` (a claim id in that note, or `null`). Doubt targets are frontmatter data, not wikilinks.

Rules:

- `doubts`, when present, is a list (`doubts-shape`). Each entry is a mapping with `mode`, `claim` and `rationale` (`doubt-shape`).
- On a `disagreement` doubt that has a `target` key, `target` is a mapping with `to` and `claim` (`doubt-target-shape`). A `disagreement` doubt with no `target` is valid.
- `target.to` stays inside the tiromex folder (`path-confinement`), ends with `.md`, and names an existing note file (`dangling-doubt-target`).

| Mode | Use when... |
|---|---|
| `disagreement` | Another claim reaches the opposite conclusion. Often paired with a `contradicts` relation. |
| `regress` | The claim rests on a premise that itself needs justification. |
| `context-relative` | The claim holds only in a context the note does not fully state. |
| `assumption` | An unstated premise does load-bearing work. |
| `circular` | The claim smuggles its conclusion into its premises. |

If claim `c1` of note A has a `disagreement` doubt targeting claim `c1` of note B, and the reverse also holds, the pair is an aporia whether or not an `aporia` note exists.

### 7.6 Review tracking

`processed` and `reviewed` record whether a human has looked at the note in its current state. They are markers, not gates. No operation waits for review.

- Every tool-drafted note starts `processed: false`. An automated change to its claims or doubts resets it to `false`.
- Rule-driven `assent` and `lifecycle` transitions, new outbound links and retagging do NOT reset it.
- A human review sets `processed: true` and `reviewed: <now>`.
- When `reviewed` and `updated` are both readable, `reviewed` older than `updated` fails `stale-review`.

## 8. Backmatter: relations and parent

Relations between notes, the parent index, and sources live in the backmatter as `- key:: value` lines (Dataview inline fields).

### 8.1 Relation vocabulary

The relation keys are a closed list of ten. Do not invent new ones.

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

`parent` (section 3.3) and `source` (section 9) are backmatter keys too, but not relations. tx reads no other backmatter key as a relation.

**Transitivity.** `requires`, `broader-than` and `narrower-than` MUST NOT form a cycle among the concept notes, directly or through any chain (`transitive-cycle`). The validator reports one cycle per relation, on the first note of the cycle.

**Conflict shapes.** A detected conflict between two claims resolves into exactly one of three shapes:

- **aporia**: neither side wins. `disagreement` doubts on both sides, and optionally an `aporia` note that links to both with `contradicts`.
- **refine**: the new claim qualifies the old one. The new note is `narrower-than` the old.
- **supersede**: the new claim replaces the old one. The new note `supersedes` the old, and the old note moves to `assent: rejected`.

### 8.2 Link form

Every relation and `parent` value is a list of titled wikilinks:

```markdown
- supports:: [[notes/tiromex/20260301093210|Retries need a budget]], [[notes/tiromex/20260302101500|Timeouts bound the damage]]
- contradicts:: [[notes/tiromex/20260220221500|Every call must be served]]
- parent:: [[notes/tiromex/20260301090000|§ Resilience]]
```

- **One line per key.** A relation with several targets joins the wikilinks with `, ` on that one line. Never repeat a key: `bim format` rewrites a repeated backmatter key into a Python list literal. A reader still accepts a hand-written repeated key.
- **Titled.** Each link has the form `[[<target>|<title>]]`. A link with no title, an empty title or a blank title (`[[t]]`, `[[t|]]`, `[[t| ]]`) fails `link-shape`.
- **No `.md`.** The target is the vault-relative path of the note without the extension: `notes/tiromex/20260411145300`.
- **No `#`.** A target never holds a heading or block anchor.
- A key with no wikilink in its value fails `link-shape`.
- Links are found by pattern, never by splitting on commas, so a title may hold a comma. When writing a title, tools drop the characters `"`, `\`, `[`, `]` and `|`: bim's backmatter reader does not escape them.
- Every target stays inside the tiromex folder after symlinks are resolved (`path-confinement`). A relation target on a concept note names an existing note file (`dangling-link`). A `parent` target names an existing note file (`dangling-moc`).

Index notes may carry relation keys and `parent` too. The same link-shape and confinement rules apply.

## 9. Sources

Source documents do not live in the vault. A concept note names the source it came from with a `source` line in the backmatter:

```markdown
- source:: mirror:articles/2026/resilience-patterns.md
```

- Each value has the form `mirror:<root>/<path>`. `<root>` names a source mirror. `<path>` is a relative path inside it.
- Several sources share one line, comma-joined: `- source:: mirror:articles/a.md, mirror:books/b.md`. A value splits before every later `mirror:`, so a path may hold a comma that is not followed by `mirror:`.
- A value that does not start with `mirror:`, has no `/` after the root name, or whose path is absolute or holds a `..` part fails `source-shape`.

This version checks the shape only. It does not resolve a mirror path to a file.

## 10. Tags

`tags` is a list of free domain descriptors in the owner's vocabulary, kebab-case. Hierarchical tags use `/`: `lang/rust`.

- A tag holding `:` is a legacy namespace tag and fails `legacy-colon-tag`.
- The tags `person` and `book` are reserved for bim's contact and book templates, so a note mover never relocates a tiromex note by accident. They fail `forbidden-tag`.

## 11. Body shape

### 11.1 H1 rule

Exactly one H1 per note (`h1-exactly-one`). An H1 is a line that starts with `#`, then a space or tab, then text. Its text equals `title` exactly (`h1-title-mismatch`). No decorative prefixes, no trailing dates.

### 11.2 Size

A concept or index note holds at least one non-blank line besides the H1 (`empty-body`) and at most `tx.max_zettel_body_lines` non-blank lines, H1 included (default 60, `oversized-body`). Blank lines do not count. Run notes have no size limit.

### 11.3 Concept note body

`thesis` and `argument` notes prefer the Socratic shape:

```markdown
# Title that mirrors the H1

## Claim
One or two sentences, in the vault's voice.

## Assumptions
What must be true for this to work.

## Evidence
Main support, plus the strongest objection.

## Implications
What this changes about how you act, decide, or design.
```

Other concept types use lighter shapes:

- `observation` and `example`: one or two paragraphs.
- `question`: the question, then what has already been considered.
- `aporia`: names the disagreement. Its backmatter links both sides with `contradicts`.

The body is paraphrased into the vault's voice, not copied from the source. Quote only when the exact wording matters, with a Markdown blockquote followed by commentary.

## 12. Validation rules

`bim tx validate` runs every rule below over every note in the tiromex folder. Each failure is reported as `<path>: [<rule>] <message>`. Rules that need one note run per file, in path order. The graph rules (`parse-error`, `path-confinement`, `dangling-link`, `dangling-moc`, `dangling-doubt-target`, `transitive-cycle`) run over the whole folder. A file that fails `parse-error` is left out of the graph.

| Rule id | Kinds | Fails when |
|---|---|---|
| `parse-error` | all | the file cannot be read, or has no frontmatter block at the start, or its frontmatter or backmatter does not parse |
| `required-field` | all | `id`, `title`, `date` or `type` is missing or blank |
| `publish-true` | concept, index, run | `publish` is `true` |
| `legacy-colon-tag` | concept, index, run | a tag contains `:` |
| `forbidden-tag` | concept, index, run | a tag is `person` or `book` |
| `h1-exactly-one` | concept, index, run | the body does not hold exactly one H1 |
| `h1-title-mismatch` | concept, index, run | there is one H1 and its text differs from `title` |
| `empty-body` | concept, index | the body holds no line other than the H1 |
| `zettel-id-format` | concept, index, run | `id` is not exactly 14 digits |
| `id-filename-mismatch` | concept, index, run | `id` differs from the file stem |
| `id-created-mismatch` | concept, index, run | `id` is well formed, `date` is readable, and `id` equals the digits of `date` neither in the value's own offset nor in the local zone |
| `type-species` | concept | `type` is not one of the section 6 types |
| `concept-type-enum` | concept | `concept-type` is not one of the section 7.1 values |
| `assent-enum` | concept | `assent` is present and not one of the section 7.2 values |
| `lifecycle-enum` | concept | `lifecycle` is present and not one of the section 7.3 values |
| `claims-shape` | concept | `claims` is present and not a list |
| `claim-shape` | concept | a claim is not a mapping with `id` and `statement` |
| `claims-required` | concept | the concept type is `thesis`, `argument` or `observation` and `claims` is missing, null or empty |
| `aporia-no-claims` | concept | the concept type is `aporia` and `claims` is a non-empty list |
| `claims-count` | concept | `claims` holds more than 3 entries, or is an empty list on a concept type that is neither claim-bearing nor `aporia` |
| `doubts-shape` | concept | `doubts` is present and not a list |
| `doubt-shape` | concept | a doubt is not a mapping with `mode`, `claim` and `rationale` |
| `doubt-mode-enum` | concept | a doubt `mode` is not one of the five modes |
| `doubt-target-shape` | concept | a `disagreement` doubt has a `target` key, and `target` is not a mapping with `to` and `claim` |
| `link-shape` | concept, index | a relation or `parent` value holds no wikilink, or a link has a blank title, or a link target ends with `.md` or holds `#` |
| `source-shape` | concept | a `source` value does not start with `mirror:`, has no `/` after the root name, or its path is absolute or holds `..` |
| `path-confinement` | concept, index | a relation target, `parent` target or doubt target (concept only) leaves the tiromex folder |
| `dangling-link` | concept | a confined relation target is not an existing file |
| `dangling-moc` | concept, index | a confined `parent` target is not an existing file |
| `dangling-doubt-target` | concept | a confined doubt `target.to` does not end with `.md` or is not an existing file |
| `orphan-concept` | concept | the note has no `parent` link |
| `oversized-body` | concept, index | the body holds more non-blank lines (H1 included) than `tx.max_zettel_body_lines` |
| `stale-review` | concept, index | `reviewed` and `updated` are both readable and `reviewed` is older |
| `transitive-cycle` | concept | `requires`, `broader-than` or `narrower-than` forms a cycle |
| `index-title` | index | `title` does not start with `§ ` |
| `members-block` | index | the members markers are neither absent nor exactly one open marker followed later by exactly one close marker |

Plain notes get only `parse-error` and `required-field`.

## 13. Complete examples

### 13.1 Concept note

````markdown
---
id: 20260411145300
title: Circuit breakers trade tail latency for systemic recovery
date: 2026-04-11T14:53:00+02:00
tags:
  - resilience
  - circuit-breaker
type: note
publish: false
processed: false
concept-type: thesis
assent: tentative
lifecycle: literature
updated: 2026-04-11T15:02:14+02:00
claims:
  - id: c1
    statement: A circuit breaker cuts the latency tail of a call chain by failing fast on a broken downstream.
  - id: c2
    statement: The cost of the pattern is a measurable false-open rate during recovery.
doubts:
  - mode: context-relative
    claim: c1
    rationale: Holds only when failing fast is acceptable to the caller.
  - mode: disagreement
    claim: c1
    target:
      to: notes/tiromex/20260220221500.md
      claim: c1
    rationale: That claim says every call must be served, which turns latency into error rate.
---

# Circuit breakers trade tail latency for systemic recovery

## Claim

A circuit breaker cuts the latency tail of a call chain by failing fast on a broken downstream, at the cost of some legitimate calls while it is open.

## Assumptions

- The downstream's failures are correlated in time.
- Failing fast is better than retrying for this workload.

## Evidence

The source cites p99 latency dropping from 4 seconds to 200 ms on a flaky downstream. The strongest objection: where every call must be served, the breaker moves the problem from latency to error rate.

## Implications

A strong fit for the booking flow. A worse fit for payments.

---

- parent:: [[notes/tiromex/20260301090000|§ Resilience]]
- supports:: [[notes/tiromex/20260301093210|Retries need a budget]]
- contradicts:: [[notes/tiromex/20260220221500|Every call must be served]]
- source:: mirror:articles/2026/resilience-patterns.md
````

### 13.2 Index note

````markdown
---
id: 20260301090000
title: § Resilience
date: 2026-03-01T09:00:00+01:00
tags:
  - resilience
type: index
publish: false
processed: false
---

# § Resilience

How systems keep serving when parts of them fail.

<!-- tx:members -->
- [[notes/tiromex/20260411145300|Circuit breakers trade tail latency for systemic recovery]]
- [[notes/tiromex/20260301093210|Retries need a budget]]
<!-- /tx:members -->
````

### 13.3 Run note

````markdown
---
id: 20260412060000
title: Tiromex run 2026-04-12
date: 2026-04-12T06:00:00+02:00
tags: []
type: tx-run
publish: false
processed: false
---

# Tiromex run 2026-04-12

Read 1 source. Created notes/tiromex/20260411145300.md. One conflict, resolved as aporia.
````

## 14. Authoring rules of thumb

- One note, one idea. Split a note that grows unrelated sections.
- The H1 is the elevator pitch. It stands alone in an index.
- New concept notes start `assent: tentative`, `lifecycle: fleeting`, `processed: false`. Promotion is a separate maintenance act.
- `thesis`, `argument` and `observation` notes carry one to three claims with stable local ids. `aporia` notes carry none.
- Attach doubts to a claim id, or to the whole note with `claim: null`. Name a foreign claim only through `target`.
- Every concept note links to an index note with `parent`.
- Write each backmatter key once. Join several links with `, `. Every link is titled, without `.md` and without `#`.
- Never put a `---` line in the body. Never leave a concept or index body empty under its H1.
- Never invent a new `type`, `concept-type`, `assent`, `lifecycle`, doubt mode or relation without changing this spec first.
- Never set `publish: true`. Only the owner may expose a note.

## 15. Compatibility notes

- **bim.** A tiromex note is a bim note. `bim format` rewrites it with the same formatter tx uses, and may add default keys (section 5.1).
- **Obsidian.** Frontmatter fields show in the Properties pane. Titled wikilinks resolve and render.
- **Dataview.** Backmatter lines are Dataview inline fields, so `supports`, `parent` and `source` are queryable. Queries on `concept-type` need bracket syntax: `WHERE row["concept-type"] = "thesis"`.
- **Git.** Every note is plain text.
- **Unknown keys.** Keys this spec does not name are tolerated and kept on rewrite.
