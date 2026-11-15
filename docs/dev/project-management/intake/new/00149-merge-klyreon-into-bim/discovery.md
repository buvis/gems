# Discovery: bim absorbs klyreon as `bim tx`, with tiromex and mirror roots

## Classification

Depth: comprehensive | Date: 2026-11-15

Source: `idea.md`, `qa-log.md` and `port-plan.md` beside this file. The port
plan holds the row-by-row verdict for every klyreon command, rule and file.
This discovery replaces the stance in
`docs/dev/project-management/research/00073-klyreon-cli.md` that any `~/bim`
integration is a permanent non-goal (lines 7, 43, 145) and that its
constraints are binding (lines 50, 54, 57). Where the two disagree, this
document wins.

## Problem

Two gems tools keep personal knowledge with overlapping words and different
rules. bim is the hand-written vault; klyreon is an LLM-kept store of claims
drawn from sources. Both use 14-digit ids, the same eight note types and the
verbs `ingest` and `create`/`new`, yet neither doc mentions the other, and
articles have two capture paths. The owner wants one tool: klyreon's engine
(claims, contradiction checks, promotion, pruning, schedule) becomes part of
bim, writes bim-format notes into a folder where agents work without asking,
reads sources from the owner's mirror of captured content, and uses any
configured LLM, local or agentic. klyreon is not in use today (its config
points at a deleted temp dir), so the merge costs no data migration on the
klyreon side.

## Requirements

### Must have

**tiromex (agent folder)**

- **M1 tiromex folder**: `<path_zettelkasten>/tiromex/` is the agent area. Any
  agent may read and write there without asking. bim exposes the folder name
  as a setting (default `tiromex`).
- **M2 Skill exception**: `src/tools/bim/SKILL.md` keeps its approval rule for
  the rest of the vault and states the tiromex exception, plus a tiromex
  section: concept fields, closed vocabularies, claim and doubt rules,
  conflict shapes, `bim tx` commands. The klyreon skill pack is not ported.
- **M3 tx scope = tiromex**: every `bim tx` rule (validate, claim index,
  promotion, MOC sync, pruning) reads and writes only inside tiromex. Notes
  outside it never carry claims and never reach an LLM through tx.
- **M4 Visible to bim**: tiromex notes appear in `bim query`, `show`, `format`
  and the other note commands like any note.

**Format (folded into bim's note format)**

- **M5 One format**: tiromex notes are bim notes: `id`, `title`, `date`,
  `tags`, `type`, `publish`, `processed` in bim order, H1 = title, backmatter
  after the last `---`. Concept notes add `concept-type`, `assent`,
  `lifecycle`, `claims`, `doubts`, `updated`, `reviewed`, `delivered-as` with
  klyreon's closed vocabularies and rules (claims required on thesis,
  argument and observation, none on aporia, one to three per note).
- **M6 Relations in backmatter**: one key per relation, value a wikilink with
  the vault path and title: `- supports:: [[notes/tiromex/<id>|Title]]`. Same
  ten relations; the transitive-cycle check stays.
- **M7 MOCs as index notes**: a MOC is a bim note of `type: index` with a `§`
  title in tiromex; a member note links to it with `- parent::`. The members
  block is marked `<!-- tx:members -->` and only that block is rewritten.
- **M8 Doubt targets**: `doubts[].target.to` is a vault-relative note path
  inside tiromex.
- **M9 Source citation**: `- source:: mirror:<root>/<path>`. bim resolves it
  through the configured mirror roots.
- **M10 Run journal**: each ingest and maintain run writes one note in
  `tiromex/runs/` of a new bim type `tx-run`, committed with the run.
- **M11 Never emit** `person` or `book` tags, `publish: true`, or colon
  namespace tags.
- **M12 Spec doc**: the klyreon format spec is revised into bim's docs as the
  tiromex format; `bim tx validate` enforces it.

**Mirror roots**

- **M13 Named roots**: bim settings list named mirror roots, each with a path.
  Names are shared; paths are machine values on the machine-local config
  layer (`~/.local/.config/buvis/buvis-bim.yaml`). The git mirror
  `~/git/src/gitlab.com/buvis/mirror` is one root; local-only directories
  may be others.
- **M14 Read-only**: bim and tx never edit, move or delete a file in a mirror
  root that an exporter owns (`clippings/`, `pocket/`, `readwise/`,
  `readwise-unofficial/` today).
- **M15 Not on this host**: a `mirror:` value whose root is not configured or
  not present on this machine is reported as "not on this host", never as a
  dangling link; rules that need the source text skip that note.
- **M16 Articles into the mirror**: `bim create -t article` writes the
  original into a folder of the git mirror, commits only that path under the
  bim identity (no push), and writes `- article:: mirror:<root>/<path>` on the
  summary note. `path_articles` retires.
- **M17 Article migration**: a command moves every original under the old
  `path_articles` into the mirror, rewrites each `article::` link in the vault
  to the `mirror:` form, and has `--dry-run`. It never overwrites a file and
  reports each skip.

**Shared LLM backend layer**

- **M18 One layer**: bim has one backend registry used by `bim tx` and
  `bim doc`. A call is text in, schema-checked JSON out; the backend gets no
  vault path and no tool access.
- **M19 Backend families**: local HTTP (Ollama, llama.cpp, any
  OpenAI-compatible endpoint), named agent-CLI adapters (claude ported from
  klyreon with `--tools ""`, others such as codex), and a generic command
  driver (argv from config, prompt on stdin, JSON on stdout). Backends are
  named in config; tx and doc each pick one by name.
- **M20 Closed errors**: every backend failure maps to `timeout`, `exit`,
  `parse` or `schema`.
- **M21 doc moves over**: `bim doc` classifier and extractor run on the shared
  layer with today's Ollama defaults unchanged for existing configs.

**`bim tx` commands**

- **M22 Commands**: `bim tx new`, `validate [--json]`, `export-claims
  [--out]`, `status`, `ingest [PATH] [--backend] [--max-sources] [--timeout]
  [--dry-run]`, `maintain [--dry-run]`, `schedule install [--at] | status |
  uninstall`. Behaviour per `port-plan.md`.
- **M23 Ingest from mirrors**: ingest walks the mirror roots, sorted by root
  then path, takes up to `max_sources_per_run`, and records each ingested file
  (root, path, content hash) in bim state under `$XDG_STATE_HOME/bim/tx/`. A
  changed hash makes the file pending again. Files with or without
  frontmatter are accepted.
- **M24 Ingest safety**: per-source staging with byte-for-byte rollback, one
  scoped commit per source under the tx identity, a per-vault lock shared with
  maintain, the git gate (refuse outside a work tree), every backend-returned
  path confined to tiromex, and a bad conflict target failing only its
  source. `--dry-run` writes nothing anywhere.
- **M25 Maintain**: lint, lifecycle promotion, assent transitions, MOC sync,
  prune detection, in that order, each transition its own scoped commit;
  idempotent; `--dry-run` writes nothing.
- **M26 Pruning**: off by default. A candidate must also have no inbound link
  from outside tiromex. A note's own source does not count as corroboration.
- **M27 Schedule**: launchd label `net.buvis.bim.tx` on macOS, a
  `# bim-tx-managed` crontab line on Linux, command
  `bim tx ingest; bim tx maintain`, `PATH` captured at install, output logged
  (macOS `~/Library/Logs/bim/tx.log`).
- **M28 Settings**: a `tx:` block in `buvis-bim.yaml` with klyreon's
  thresholds (same names and defaults), `backend` (a name from M19) and
  `git_identity_name`/`git_identity_email` (defaults `bim-tx`,
  `bim-tx@localhost`), used by every tx commit.
- **M29 Staleness**: only `bim tx` commands warn when maintain has not run
  within `maintenance_window_days`.
- **M30 All interfaces**: `tx status`, `validate`, `ingest` and `maintain` are
  command classes returning `CommandResult` and are registered in the serve
  action registry (`src/tools/bim/commands/serve/_actions.py`) and the TUI.

**Retirement**

- **M31 Remove klyreon**: entry point, wheel package, pytest marker, docs page,
  `docs/reference/klyreon/` (format spec revised under bim, philosophy docs
  moved), tests, and the local leftovers (`~/.config/klyreon/`,
  `~/.local/state/klyreon/` with its ~270 stale lock files, the dotfiles
  ledger entry). The checklist is the Retirement block in `port-plan.md`.

### Nice to have

- `bim show` and serve render a `mirror:` value as a link to the resolved file
  on hosts that have the root.
- The claim index is rebuilt after each committed source, so sources in one
  run can conflict with each other.
- Obsidian click-through for `mirror:` values (a URI handler or a Dataview
  helper).

### Out of scope

- Writing to exporter-owned mirror folders, or running the exporters
  (readerctl, clippers).
- Seatbelt or any OS-level fence around `~/bim`; the skill text is the gate.
- Hand-written notes outside tiromex carrying claims (per-note opt-in
  rejected).
- Query with citations and the deliver roadmap from 00073.
- Enforcing the prompt-only rules (claim word count, banned words).
- Token or spend accounting.
- Pushing the mirror repo or the vault.

## Constraints

- One binary, one vault: no `klyreon` command, no second root config, no
  `~/.config/klyreon/`. Config lives in `~/.config/buvis/buvis-bim.yaml`, and
  machine values in `~/.local/.config/buvis/buvis-bim.yaml`.
- The machine-local layer (PRD 00122) is on branch
  `feature/config-local-layer-braid`, not master. The mirror phase waits for
  it to land, or carries the layer itself (create-prd decides).
- Every write uses `pybase.filesystem.atomic_write`; every commit names exact
  paths; never `git add -A`; never touch global git config.
- The library stays interface-agnostic: the tx engine and the LLM layer live
  under `src/tools/bim/`, not `src/lib/`, unless they have a second consumer.
- No new runtime dependency for the HTTP backends (stdlib `urllib` or the
  existing client in `bim doc`).
- Never read the private vault in tests; use a scratch dir through
  `BUVIS_BIM_PATH_ZETTELKASTEN` and isolate `XDG_STATE_HOME`.
- Command layer returns `CommandResult`; CLI renders with `console`; no
  `print`/`click.echo`.
- Obsidian's Linter and Auto Note Mover act on files: tx output must already
  pass the Linter and never carry `person`/`book` tags.

## Codebase Context

- **Relevant code (source)**: `src/tools/klyreon/` (6,730 lines, 53 files):
  `spec/` (parser, writer, model, validator), `vault/` (config, paths, ids,
  git, state), `ingest/` (pipeline, render, conflicts, moc), `run/` (staging,
  lock, trail), `maintain/` (sweep, rules, graph, moc_sync, prune),
  `backends/` (base, claude, stub), `schedule/` (launchd, cron, installer),
  `prompts/ingest.md`. Tests: `tests/tools/klyreon/` (5,305 lines).
- **Relevant code (target)**: `src/tools/bim/cli.py` (group, `--skill`),
  `src/tools/bim/settings.py` (`BimSettings`, `path_articles` at line 22),
  `src/tools/bim/shared/article_archive.py` (article archive path),
  `src/tools/bim/commands/create_note/create_note.py`,
  `src/tools/bim/commands/doc/shared/llm.py` and `settings_models.py:130`
  (`ClassifierSettings`, Ollama/llama.cpp), `src/tools/bim/SKILL.md`
  (approval rule lines 17-22, vault format 193-357), the zettel model in
  `src/lib/buvis/pybase/zettel/` and Rust `src/rust/src/types.rs`.
- **Conventions**: command groups with a `shared/` subdir (`bim doc` is the
  model); lazy imports in CLI handlers; class-based tests mirroring `src/`;
  markers by path.
- **Integration points**: `BimSettings` gains `tx`, `mirrors`, `llm`
  (backends) blocks and loses `path_articles`; `bim create -t article` path;
  `ACTION_HANDLERS` in `commands/serve/_actions.py:221`; bim type vocabulary
  gains `tx-run`; `bim format` must keep concept fields and backmatter
  relations (round trip measured in `idea.md`).
- **Similar implementations**: `bim doc` (unattended pipeline, LLM step,
  state under `$XDG_STATE_HOME/bim/doc`, triage in the action registry);
  klyreon's own scoped git layer and launchd installer.
- **Facts checked 2026-11-15**: `~/bim` is a git work tree; no klyreon skill,
  plist or live vault exists; the mirror repo has four exporter folders.

## Approach

- **Chosen**: fold klyreon into bim in six phases (`port-plan.md`):
  1. tiromex and the folded format (`bim tx new/validate/export-claims/status`,
     skill exception);
  2. shared LLM backend layer, `bim doc` moved onto it;
  3. mirror roots, articles into the git mirror, article migration;
  4. `bim tx ingest` (depends on 1-3);
  5. `bim tx maintain`, schedule, serve and TUI actions (depends on 4);
  6. retire klyreon (depends on 5).
  Phases 1-3 are independent; numbering is execution order. Six PRDs is an
  estimate, not measured.
- **Why**: one tool and one vault, as the owner asked; tiromex gives agents a
  free area without loosening the rest of the vault; reading mirrors in place
  respects exporter ownership; one LLM layer avoids two backend stacks.
- **Rejected alternatives**:
  - Fold klyreon's commands under `bim` with its own vault and format: one
    binary with two vaults, two formats and two `ingest` verbs.
  - Share only the zettel model: one to two PRDs to dedupe one YAML loader;
    the overlap stays.
  - Docs-only "bim or klyreon?" guidance: overtaken by the one-tool decision.
  - Keep sources inside the vault (klyreon's `sources/` + archive move):
    exporters own the mirror files and rewrite them.
  - A tx-only subfolder inside tiromex: the owner chose one shared tiromex.
  - Run journal in the state dir: per machine and not in git.
  - Frontmatter `links`/`sources` lists (klyreon form): bim and Obsidian use
    backmatter wikilinks; Dataview and the graph view read those.

## Success Criteria

- A scratch vault with a mirror root of fixture files: `bim tx ingest` with
  the claude backend and with one local model (Ollama or llama.cpp) each turn
  the fixture sources into tiromex notes that `bim tx validate` accepts, and
  each crafted conflict lands in exactly one of aporia, refine or supersede.
  Other adapters pass a smoke test.
- A killed backend call mid-ingest leaves no note, no commit, no hash record;
  the next run ingests the source cleanly.
- Editing a mirror fixture file makes it pending again; the mirror file bytes
  never change across any tx run.
- A note outside tiromex never appears in `bim tx export-claims` or in a
  prompt sent to a backend (asserted with a recording backend).
- Two `bim tx maintain` runs in a row: the second changes nothing; with
  pruning on, a note linked from outside tiromex is never deleted.
- `bim format` on a tiromex note leaves concept fields and relations intact.
- `bim create -t article` on a scratch mirror writes and commits only the
  original's path; the article migration on a fixture tree moves every file,
  rewrites every `article::`, and its `--dry-run` changes nothing.
- A `mirror:` citation to an unconfigured root is reported "not on this host"
  and does not fail validate.
- `bim doc` classification passes its existing tests on the shared layer.
- `tx status`, `validate`, `ingest`, `maintain` run from CLI, serve action and
  TUI with the same `CommandResult`.
- After retirement, `rg -i klyreon src tests docs/source pyproject.toml`
  finds nothing and CI is green.

## Risks

- **Small local models fail the large `IngestPayload` schema**: measured in
  phase 4 by the fixture suite on one local model; if it fails, split the
  call (draft notes, then conflicts) before adding retries.
- **Generic command driver cannot prove tools are off**: only named adapters
  that pass a no-tools flag may run unattended by default; the generic driver
  needs an explicit config flag that names the risk.
- **Other agents' notes in tiromex fall under tx rules**: a fleeting,
  unlinked concept note an agent left there can be pruned once pruning is on.
  Pruning stays off by default; the skill says tiromex notes follow the tx
  format.
- **Human commits mixed with machine commits in `~/bim`**: scoped paths and
  the tx identity keep them apart; ingest refuses to stage a path the human
  has uncommitted edits on (design to confirm).
- **Obsidian plugins rewrite tx files** (Linter on open): tx writes
  Linter-clean output; validate tolerates Linter's spacing.
- **`mirror:` values are not clickable in Obsidian**: accepted by the owner;
  nice-to-have covers click-through.
- **Branch drift**: `feature/config-local-layer-braid` touches
  `src/tools/klyreon/cli.py`, `bim/commands/serve/*`, `bim.rst`, `README.md`;
  merge it before phase 1 lands or expect conflicts.
- **Article migration rewrites many vault notes**: dry run first, one commit,
  and the command touches only `article::` lines.

## Open Questions

- Folder inside the git mirror for bim-written articles (`articles/`?) and its
  file naming (keep `<YYYY>/<YYYYMM>00/<title>.md`?).
- Config shape for mirror roots and backends (list vs map) and the setting
  names; design decides, following `buvis-bim.yaml` style.
- Does ingest skip a mirror file that an exporter is mid-way through writing
  (size or mtime settle check)?
- Should phase 3 wait for PRD 00122 on master, or carry the machine-local
  loader itself?
- Where do the klyreon philosophy docs go (`docs/reference/bim/` or stay
  under a renamed folder)?
- The 00149 number was picked from one unmerged branch; create-prd should
  re-check numbers across all branches before cutting PRDs.

## Discovery Log

Q1 to Q7 come from `qa-log.md` (asked earlier this session); Q8 onward were
asked during this elicitation.

### Q1: Do hand-written notes ever carry claims and join the contradiction check?
**Answer**: No. Only tiromex notes carry claims.

### Q2: General agent folder or engine folder only?
**Answer**: General, under `notes/`, named `tiromex` ("Memex as if I also had
Tiro, Cicero's secretary").

### Q3: Command group name?
**Answer**: `bim tx`.

### Q4: Where do source documents live?
**Answer**: In an archive of mirrored content (articles, book passages,
clippings, screenshots, voice). The mirror repo exists at
`~/git/src/gitlab.com/buvis/mirror`; bim has no config key for it. Mirrors
are in scope. There can be local mirrors outside git or iCloud.

### Q5: Seatbelt fence or skill text?
**Answer**: Skill text only.

### Q6: Does `bim doc` move onto the shared LLM layer?
**Answer**: Yes, one layer.

### Q7: How does tx treat mirrors; where do articles go; local-only roots; old articles?
**Answer**: Read-only, tracked by hash. `bim create -t article` writes into
the git mirror; `path_articles` retires. A missing root reads "not on this
host". Existing originals migrate and `article::` links are repointed.

### Q8: Which part of tiromex does tx own?
**Answer**: The whole tiromex root, shared by all agents. No tx-only
subfolder.

### Q9: Where does the run journal live?
**Answer**: A note in `tiromex/runs/`, new type `tx-run`.

### Q10: How does a note cite its mirror source?
**Answer**: `- source:: mirror:<root>/<path>`.

### Q11: What does `article::` hold after the move?
**Answer**: `mirror:<root>/<path>`, for new and migrated notes.

### Q12: Does bim commit articles it writes into the git mirror?
**Answer**: Yes, one scoped commit per article, no push.

### Q13: Which backends must pass the ingest fixture suite?
**Answer**: claude and one local model; other adapters get a smoke test.

### Port plan rulings
**Answer**: six drops approved one by one (init and root config, assets
group, clock offset, `oversized-body` on sources, `is_human_authored`,
klyreon `manifest.toml`); port and redesign rows approved as one table.

### Inferred (not asked)
- Since tx owns the whole tiromex root, notes other agents write there follow
  the tx format and fall under tx rules (risk listed).
- Pruning must skip notes linked from outside tiromex, because tx may not edit
  private notes to clean the inbound link.
- Mirror root paths are machine values, so they belong on the machine-local
  config layer (global rule, 2026-11-10).
- HTTP backends reuse `bim doc`'s wire code; no new dependency.
- The 00073 rule "LLM access only through operator CLIs, never raw API keys"
  is replaced: local HTTP endpoints are now first-class (Q6, decision 3 in
  `idea.md`). Hosted API keys stay out of scope; nothing asked for them.
