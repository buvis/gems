---
name: klyreon-vault
description: Use when editing, creating, or reviewing files in a klyreon Memex-Zettelkasten vault (sources/ and wiki/notes/). Covers the two file species, the closed vocabularies, claim and doubt rules, and the klyreon command surface.
---

# Working in a klyreon vault

A klyreon vault is a Memex-Zettelkasten. The **normative** format is defined in
`docs/reference/klyreon/zettel-format-specification.md` in the klyreon source
repository — read it when a detail here is not enough. This file teaches an
interactive session enough to not write files klyreon rejects; it does not
restate the spec in full.

A human session edits the vault through `klyreon new` and by hand. **klyreon's
own autonomous loop does not read this file** — the loop's prompts ship inside
the klyreon package, so the loop stays independent of anything installed into a
home directory. Changing this file changes what an interactive Claude session
knows, nothing else.

## The two file species

Every file is exactly one species, and the rules differ by species.

**Source documents** live in `sources/YYYY-MM/` (moved to `sources/archive/YYYY-MM/`
once ingest commits them). The filename is descriptive kebab-case and the `id`
field equals the filename without `.md`. The body is the external item's own
words, cleaned but otherwise unchanged. `type` is a source-document type. A
source document NEVER has `concept-type`, `assent`, or `lifecycle` — it is raw
material that has not been interrogated.

**Zettels** live in `wiki/notes/` (flat, no subdirectories). The filename is
`YYYYMMDDHHmmSS.md` — exactly 14 digits, no prefix or separators — and the `id`
field equals it without `.md`. The body is paraphrased into the vault's voice,
not copied. A **concept zettel** carries `concept-type`, `assent`, `lifecycle`,
structured `claims` when it asserts something, and `doubts` where honest doubt
exists; it participates in klyreon's operations. A **utility zettel**
(a snippet, cheatsheet, procedure) has none of those fields.

Finding a source-document type on a `wiki/notes/` file, or a zettel type on a
`sources/` file, is an error.

## Closed vocabularies

These enumerations are closed. Pick the closest fit; never invent a value
without updating the spec first.

- **Source-document `type`**: `article`, `book`, `quote`, `transcript`.
- **Zettel `type`**: `note`, `definition`, `procedure`, `wiki-article`,
  `cheatsheet`, `snippet`, `course`, `ai-prompt`. `note` is the default.
- **`concept-type`**: `thesis`, `argument`, `aporia`, `question`, `example`,
  `observation`.
- **`assent`**: `accepted`, `tentative`, `rejected`, `unknown`.
- **`lifecycle`**: `fleeting`, `literature`, `evergreen`.
- **doubt `mode`**: `disagreement`, `regress`, `context-relative`, `assumption`,
  `circular`.
- **`links` relations** (capped at ten): `supports`, `contradicts`,
  `exemplifies`, `supersedes`, `defines`, `analogous-to`, `causes`, `requires`,
  `broader-than`, `narrower-than`.

## Claims

A `claims` entry is a `{id, statement}` object. The `id` is local to the zettel
(convention `c1`, `c2`, …), never globally unique, and never changes after
creation — `doubts` reference it. The `statement` is a one-sentence assertion in
plain language: no hedging, no "but" or "however" (split those into two claims,
or move the nuance into a doubt).

- A concept zettel of `concept-type: thesis`, `argument`, or `observation`
  **MUST carry at least one claim** — claims are the substrate of contradiction
  detection, and an assertion-bearing zettel without a claim is invisible to it.
- A `question` zettel usually carries no claim (its body is a question).
- An `aporia` zettel carries **NO claims of its own** — it references the
  disagreeing claims via `contradicts` links plus a scope-level `disagreement`
  doubt. Restating the two claims inside the aporia would pollute the claim set.

## Doubts

A `doubts` entry records honest skepticism as `{mode, claim, target?, rationale}`:

- `mode` is one of the five modes above.
- `claim` is the local claim `id` the doubt attaches to, or `null` for a
  scope-level doubt about the whole zettel.
- `target` is OPTIONAL — the foreign claim the doubt is raised against, as
  `{to: <root-relative path>, claim: <local id or null>}`. It is required on
  `mode: disagreement` when the disagreement is with material elsewhere in the
  wiki, and is the only place a claim outside the current zettel may be named.
- `rationale` is one or two sentences. If it needs more, it has earned its own
  zettel — link there instead.

## The three conflict shapes

When a new claim conflicts with an existing one, it resolves into **exactly one**
of three shapes, never silent coexistence:

1. **Aporia** — neither side wins: a `disagreement` doubt on each side (and
   optionally an `aporia` zettel). Derivable from the doubts graph when the two
   `disagreement` doubts target each other.
2. **Refine** — the new claim qualifies the old one: a `narrower-than` link.
3. **Supersede** — the new claim replaces the old one: a `supersedes` link, and
   the superseded zettel moves to `assent: rejected`.

## The klyreon command surface

```bash
klyreon init [PATH]                  # create the vault skeleton + config
klyreon new --title "…" --type note --concept-type thesis   # one spec-valid zettel
klyreon new --title "ripgrep tip" --type snippet            # a utility zettel
klyreon validate                     # every mechanical check; exit 1 on any error
klyreon validate --json              # machine-readable report on stdout
klyreon export-claims                # claim index as JSON on stdout
klyreon status                       # vault dashboard, computed on demand
klyreon assets install [--operator claude]   # install/refresh this asset pack
klyreon assets status                        # what is installed and whether it is current
klyreon assets refresh                       # bring installed packs up to the running CLI
klyreon assets uninstall [--operator claude] # remove klyreon's files, keep edited ones
```

Create a zettel with `klyreon new` (it allocates a collision-free 14-digit id
and writes a spec-valid file) rather than hand-building the filename. Run
`klyreon validate` before considering an edit done — it exits non-zero on any
rule violation and tells you which rule broke.
