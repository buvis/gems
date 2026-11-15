# bim: absorb klyreon, with a recognised agent folder in the vault

Status: recorded 2026-11-15. Pre-discovery. Nothing is designed or built.

Number 00149 is the next free one after 00148 on branch
`feature/config-local-layer-braid` (not merged to master on 2026-11-15). Other
unmerged branches were not checked for higher numbers.

This file records what one working session found and what the owner decided.
It feeds a discovery doc. It reverses the stance in
`docs/dev/project-management/research/00073-klyreon-cli.md` that any `~/bim`
integration is a permanent non-goal (lines 7, 43, 124, 145 there).

Line numbers were checked on branch `feature/merge-klyreon-to-bim` at
`18429bfe` unless a line says otherwise.

## Problem

By design the two tools do different jobs. bim is the hand-written vault (GTD,
PARA, projects, meetings, contacts, Jira). klyreon is an LLM-kept knowledge
base of claims drawn from sources. The split is written down only in the 00073
discovery. Users and agents see an overlap:

- `docs/source/tools/klyreon.rst` never mentions bim; `docs/source/tools/bim.rst`
  never mentions klyreon. `docs/source/tools.rst:34` and `:49` call both a
  Zettelkasten.
- Articles have two paths: `bim create -t article` (archive the original, write
  a summary note) and klyreon `sources/` plus `klyreon ingest`. Same for books,
  quotes, transcripts.
- All 8 klyreon zettel types (`note`, `definition`, `procedure`,
  `wiki-article`, `cheatsheet`, `snippet`, `course`, `ai-prompt`) are bim types
  too. Both use 14-digit ids and a `processed` flag.
- Same verbs, different jobs: `bim doc ingest` (file PDFs) and `klyreon ingest`
  (sources to zettels); `bim create` and `klyreon new`.
- The bim skill (`src/tools/bim/SKILL.md:3`) triggers on "zettel" and "query the
  vault". The klyreon skill
  (`src/tools/klyreon/assets/payload/claude/skills/klyreon/SKILL.md`) never says
  "not for `~/bim`", and its command list lacks `ingest`, `maintain`, `schedule`.
- `README.md:70` lists "All 16 CLIs" without klyreon.
- klyreon keeps its vault root in `~/.config/klyreon/config.yaml`, against the
  rule that gems tools keep config in `~/.config/buvis/buvis-<tool>.yaml`.

## Decisions (owner, verbatim, 2026-11-15)

1. "what if klyreon adopted bim's formating standards, but lived as a separate
   folder within bim's vault? That way we could gate LLMs access and say that a
   given folder is free for LLMs to play - that would also change bim's skill
   instruction of always needing approval. In the end, I don't care if agents
   have a recognized area where they are free"
2. "I don't mind including generated notes in bim query, etc. Actually, I want
   to be more ambitious and have just bim going forward"
3. "about LLM backends: this must be configurable, meaning that local models
   can be used and any other agentic driver can be used as well, not only
   claude"

## Proposal (agent's reading of the three decisions)

klyreon stops being a tool. Its engine becomes a bim feature. Machine-written
notes use bim's note format and live in a recognised agent folder inside the
bim vault. Agents may read and write that folder without asking. Everything
else in the vault keeps today's approval rule. The LLM step takes any
configured backend.

## What the code already gives us

- **Size.** klyreon: 6,730 lines of Python in 53 files, 5,305 lines of tests.
  bim: 12,942 lines of Python, frontend not counted. The klyreon `spec/` and
  `vault/` packages are 1,451 lines together. (Raw line counts, taken on the
  braid branch.)
- **No shared model today.** klyreon imports nothing from `pybase.zettel`. Its
  parser says so on purpose (`src/tools/klyreon/spec/parser.py:3`). It uses
  pybase only for console, settings, `CommandResult` and atomic writes.
- **bim's model can hold klyreon's data.** Frontmatter is an ordered map of
  nested YAML values and backmatter is a second map
  (`src/rust/src/types.rs:7`). Claims and doubts fit the first. Typed relations
  fit the second.
- **Round trip measured.** The installed `bim format` (mise `pipx-buvis-gems`,
  version not recorded, not this branch's build) was run on the sample at the
  end of this file. All frontmatter data and all four backmatter relations
  survived. Two layout changes: nested list items lose their two-space indent,
  and a plain string longer than 80 columns is wrapped onto a continuation
  line. The wrapped YAML parses to the same string. `bim format PATH` printed
  the result and left the file as it was.
- **The unattended LLM cannot touch files.** The claude adapter runs
  `claude -p --json-schema ... --tools ""` in a throwaway directory
  (`src/tools/klyreon/backends/claude.py:3`). The contract gives the backend no
  vault path (`src/tools/klyreon/backends/base.py:228`). The model sees only
  the text klyreon puts in the prompt.
- **Git works from a subfolder.** klyreon needs only to be inside a work tree
  and commits exact paths with `git -C <root>`
  (`src/tools/klyreon/vault/git.py:70`, `:87`). Read from code, not run: a
  folder inside the vault's repo or a nested repo should both work.
- **klyreon rules walk only klyreon's root.** `validate`, `maintain` and
  pruning never see notes outside it.
- **bim scans `notes/` recursively** (`src/rust/src/scanner.rs:373`,
  `markdown_zettel_repository.py:119`). A folder under `notes/` shows up in
  `bim query` and in query-driven `format`, `archive`, `edit`. The owner accepts
  that (decision 2).
- **`bim doc` is the precedent.** It is a command group in bim with its own
  `shared/` code, unattended ingestion and an LLM step. Its triage actions are
  in the serve action registry
  (`src/tools/bim/commands/serve/_actions.py:177`, `:200`). Whether the other
  doc commands are in the registry was not checked.

## LLM backends (decision 3)

What exists:

- klyreon: `Backend` protocol, `run(prompt, timeout) -> IngestPayload`
  (`src/tools/klyreon/backends/base.py:228`). The registry hard-codes `claude`
  and `stub` (`src/tools/klyreon/backends/__init__.py:46`, `:68`). Settings:
  `backend: str = "claude"` and an optional `model`
  (`src/tools/klyreon/settings.py:23`).
- bim doc: `ClassifierSettings.backend` is `ollama` or `llamacpp` with an HTTP
  `endpoint` (`src/tools/bim/commands/doc/shared/settings_models.py:130`). Wire
  shaping lives in `src/tools/bim/commands/doc/shared/llm.py`.

So there are two separate backend layers. One drives an agent CLI. One calls a
local chat endpoint. Neither covers the other's family.

What the decision adds (agent's reading, to settle in discovery):

- One backend setting must reach both families: local model servers (Ollama,
  llama.cpp, any OpenAI-compatible endpoint) and agent CLIs (claude, codex,
  kiro, copilot, gemini, pi, and ones not yet known).
- The contract should stay as it is: text in, schema-checked JSON out, no file
  access. That contract is what keeps private notes out of reach.
- "Any other agentic driver" suggests a generic command driver (argv from
  config, prompt on stdin, JSON on stdout) next to named adapters. Open risk: a
  generic driver cannot prove the CLI has its tools turned off. The claude
  adapter gets that from `--tools ""`.
- Open risk: `IngestPayload` is a large schema. Small local models may fail it
  often. Nothing was measured.
- Whether `bim doc` moves onto the same backend layer is open. Before decision
  3 the agent proposed leaving the two layers apart; decision 3 may change
  that.

## Hard parts

1. **Links.** klyreon stores relations, sources and MOCs as frontmatter lists
   of root-relative paths. bim uses wikilinks and a Dataview backmatter block.
   The klyreon spec dropped that block on purpose
   (`docs/reference/klyreon/zettel-format-specification.md:175`). The change
   touches graph, prune, conflict, MOC, render, staging and validator code, the
   ingest prompt, the payload schema and every fixture. A natural mapping is
   one backmatter key per relation: `- supports:: [[...|Title]]`.
2. **Machine rules need a boundary.** Validation, promotion and pruning must
   apply only inside the agent folder. The contradiction check sends the claim
   index to the LLM, so it may hold only claims from that folder.
3. **All-interface rule.** Root `AGENTS.md` says every bim action works from
   CLI, TUI, API and WebUI. klyreon is CLI-only.
4. **Git.** `ingest` and `maintain` refuse to run outside a git work tree.
   Whether `~/bim` is one was not checked.
5. **Other writers.** Obsidian's Linter rewrites files on save. Auto Note Mover
   moves any note tagged `person` or `book`, so the engine must never emit
   those tags.
6. **Smaller format gaps.** `created` becomes `date`. Key order follows bim.
   MOCs become bim index notes with `§` titles. Source documents use kebab-case
   ids, not 14 digits. `transcript` is not a bim type. Trails (`kind: trail`)
   have no bim counterpart.
7. **Pruning leaves dangling links.** If pruning is ever on, a deleted machine
   note can still be linked from a private note. The engine cannot clean that.
8. **Migration.** Existing klyreon notes, the installed launchd or cron job,
   the installed skill pack, the manifest in `$XDG_STATE_HOME/klyreon`, the
   `BUVIS_KLYREON_*` variables. The number of existing notes is unknown.

## What can be deleted

- klyreon's parser, writer and model, once the engine uses `pybase.zettel`.
- `~/.config/klyreon/config.yaml`: the root comes from bim settings.
- The operator asset installer and the klyreon skill: `bim --skill` ships
  bim's skill (`src/tools/bim/cli.py:15`).
- The `klyreon` entry point, its settings class, its docs page.

## Phases (agent's estimate: about six PRDs, not measured)

1. **Format.** Fold the klyreon spec into bim's note format. Switch the engine
   to bim's zettel model.
2. **Agent folder.** A bim setting names it. Machine writes stay inside it. The
   skill and docs state the exception to the approval rule.
3. **Engine.** Move ingest, maintain, validate and status into bim as a command
   group beside `doc`.
4. **Intake and backends.** One path for articles: the bim inbox and
   `bim create -t article` feed ingest. The configurable backend layer lands
   here or in phase 3.
5. **Schedule and interfaces.** The scheduler runs bim. The commands join the
   action registry.
6. **Retirement.** Migrate the old vault and installed files. Remove the
   `klyreon` binary.

Options that were sized and dropped:

- Fold the commands under `bim` and keep a separate vault and format: about one
  PRD, but one binary would then hold two vaults, two formats and two `ingest`
  commands.
- Share the zettel model only: one to two PRDs for one duplicated YAML loader.
- Docs-only "bim or klyreon?" guidance: overtaken by decision 2.

## Open questions

Asked, not yet answered by the owner:

1. Should hand-written notes ever carry claims and join the contradiction
   check? The agent assumed no, because that sends their claims to the LLM. A
   yes needs a per-note opt-in.
2. Is the free area a general agent folder with the engine's notes inside it,
   or the engine's folder alone? The agent recommended general. The owner's
   wording ("a recognized area where they are free") points the same way but
   did not say so outright.

Not yet asked:

3. Where does the agent folder sit: under `notes/` (decision 2 allows it) or
   beside it?
4. Does the feature keep the name klyreon inside bim, and what is the command
   group called?
5. Do source documents stay in the vault, or follow bim's article archive
   under `path_articles`?
6. Does the skill text alone gate interactive agents, or does the Seatbelt
   profile in the dotfiles repo also fence `~/bim`?
7. Does `bim doc` move onto the shared backend layer?

## Round-trip sample

Input given to `bim format`. The folder names (`agents/klyreon/...`) are
placeholders, not a decision.

```markdown
---
id: 20260411145300
title: Circuit breakers trade tail latency for systemic recovery
date: 2026-04-11T14:53:00+02:00
tags: [resilience, distributed-systems]
type: note
publish: false
processed: false
updated: 2026-04-12T09:00:00+02:00
concept-type: thesis
assent: tentative
lifecycle: fleeting
claims:
  - id: c1
    statement: A circuit breaker raises tail latency for one caller to protect the whole system.
  - id: c2
    statement: Half-open probes bound the recovery time.
doubts:
  - mode: disagreement
    claim: c1
    target:
      to: agents/klyreon/notes/20260301101500.md
      claim: c2
    rationale: The other note argues retries with jitter recover faster.
  - mode: assumption
    claim: null
    rationale: Assumes failures are correlated across callers.
---

# Circuit breakers trade tail latency for systemic recovery

## Claim

A breaker fails fast so the system can recover.

---

- source:: [[agents/klyreon/sources/archive/2026-04/resilient-patterns|Patterns for resilient distributed systems]]
- supports:: [[agents/klyreon/notes/20260301101500|Bulkheads isolate failure]]
- contradicts:: [[agents/klyreon/notes/20260302111500|Retries with jitter recover faster]]
- parent:: [[agents/klyreon/mocs/resilience|§ Resilience]]
```
