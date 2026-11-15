# Port Plan: klyreon into bim as `bim tx`

_Freshness: generated 2026-11-15 from `src/tools/klyreon` at `e78fee4c` (last
commit touching it on `feature/merge-klyreon-to-bim`, base `18429bfe`).
Regenerate if the source has moved on since. Branch
`feature/config-local-layer-braid` changes `src/tools/klyreon/cli.py`; re-check
that diff before phase 6._

Source: klyreon (`src/tools/klyreon/`, `docs/source/tools/klyreon.rst`,
`docs/reference/klyreon/`, skill pack under `assets/payload/`). Target: bim,
command group `bim tx`, machine notes in `notes/tiromex/` (decisions in
`idea.md` and `qa-log.md` beside this file).

Terms used below:

- **tiromex**: the agent folder `<path_zettelkasten>/tiromex/`. Any agent may
  write there without asking.
- **engine folder**: the part of the vault `bim tx` rules apply to. Fixed in
  discovery Q8: the whole tiromex root, shared by all agents. Paths such as
  `notes/tiromex/tx/<id>` below read as `notes/tiromex/<id>`.
- **mirror root**: a named, read-only directory of captured content (the git
  repo `~/git/src/gitlab.com/buvis/mirror` with `clippings/`, `pocket/`,
  `readwise/`, `readwise-unofficial/`, plus local-only roots per machine).

## Inventory Matrix

Docs-first rows (from `klyreon.rst`, the skill pack and the format spec) come
first; `code-only` rows follow (from a read of the code, 2026-11-15).

### Commands and flags

| row | classification | reason | code-only |
|-----|-----------------|--------|-----------|
| `klyreon init [PATH]`, `--force` | drop | The vault already exists (`~/bim` is a git work tree, checked 2026-11-15); bim settings give the root; the engine folder is created on first write. | no |
| `init --operator`, `--no-input` | drop | Goes with `init` and the asset installer. | no |
| `init --schedule`, `--at` | drop | `bim tx schedule install --at` covers it; no setup wizard needed. | no |
| `klyreon new --title --type --concept-type` | redesign | Becomes `bim tx new`: writes a concept note in bim format into the engine folder via bim's create path (id, date, template), with tx defaults (`assent: tentative`, `lifecycle: fleeting`, starter claim). | no |
| `klyreon validate`, `--json`, exit 1 on error | redesign | `bim tx validate` checks only the engine folder, against the folded bim format (backmatter relations, `date` not `created`, index notes). Same JSON keys. | no |
| `klyreon export-claims`, `--out`, refusal under root | port | `bim tx export-claims`; refusal now covers the whole vault root. Claims come only from the engine folder (qa-log Q1). | no |
| `klyreon ingest [PATH]` | redesign | Reads from mirror roots, never moves originals, tracks each ingested file by root, path and content hash in bim state; re-ingests on hash change (qa-log). PATH names a mirror file or any file, copied nowhere. | no |
| `ingest --backend`, `--max-sources`, `--timeout`, `--dry-run` | redesign | `--backend` picks a named backend from the shared bim LLM layer; the other flags port. `--dry-run` must have no filesystem effect (today it copies, code-only row below). | no |
| `klyreon status` | port | `bim tx status`; counts scoped to the engine folder; pending = mirror files with no or stale hash record. | no |
| `klyreon maintain`, `--dry-run` | port | `bim tx maintain`; same five steps in the same order, scoped to the engine folder. | no |
| `klyreon schedule install [--at]`, `status`, `uninstall` | port | `bim tx schedule ...`; label `net.buvis.bim.tx`, cron marker `# bim-tx-managed`; runs `bim tx ingest; bim tx maintain`. | no |
| `klyreon assets install/status/refresh/uninstall` | drop | `bim --skill` already ships the bim skill (`src/tools/bim/cli.py:15`); no second skill pack, so no installer, manifest or backups. | no |

### Behaviour and settings

| row | classification | reason | code-only |
|-----|-----------------|--------|-----------|
| Vault root from `$KLYREON_ROOT` or `~/.config/klyreon/config.yaml` | drop | Root is `path_zettelkasten` from `buvis-bim.yaml`; the per-tool config dir breaks the `~/.config/buvis/` rule. | no |
| Root-relative path confinement (`..`, absolute, symlink escape rejected) | port | Same rule, root = vault root; also applied to paths the backend returns (code-only gap below). | no |
| Settings `max_sources_per_run`, `source_timeout_seconds`, `max_zettel_body_lines`, `maintenance_window_days`, `pruning_enabled`, `prune_window_days` | port | Same names and defaults under a `tx:` block in `buvis-bim.yaml`; env `BUVIS_BIM_TX__*`. | no |
| Settings `backend`, `model` | redesign | Replaced by a reference to a named backend in the shared bim LLM layer (local HTTP endpoints and agent CLIs, qa-log Q7). | no |
| Settings `git_identity_name`, `git_identity_email` | port | Defaults become `bim-tx` / `bim-tx@localhost`; now used by ingest too (code-only bug below). | no |
| Staleness warning on every command | redesign | Only on `bim tx` commands, not on every `bim` call; text fixed (says "once it ships" today). | no |
| Git autonomy gate: ingest and maintain refuse outside a git work tree | port | `~/bim` is a git work tree; keep the gate. | no |
| Scoped commits: exact paths, machine identity, unsigned, env override | port | Mandatory in a vault the owner also commits to; never `git add -A`. | no |
| Single-instance lock per vault | port | Same flock; lock path under `$XDG_STATE_HOME/bim/tx/`. | no |
| Atomic per-source staging and byte-for-byte rollback | port | Unchanged mechanics; staging under `$XDG_STATE_HOME/bim/tx/staging/`. | no |
| Archive-first source move (`sources/YYYY-MM` -> `sources/archive/`) | redesign | Mirror files are exporter-owned and read-only; the hash record replaces the move as "ingested" marker. | no |
| Run journal (trail note under `wiki/trails/`) | redesign | A note of new bim type `tx-run` in `tiromex/runs/`, committed with the run (discovery Q9). | no |
| Voice file `<root>/voice.md` with built-in default | port | Moves into the engine folder; the starter placeholder text is not sent as the voice (code-only bug below). | no |
| Ingest prompt shipped in package | port | Updated for bim format; still never reads an installed skill. | no |
| Lifecycle promotion rules | port | Unchanged rules. | no |
| Assent transition rules, open disagreement holds | port | Unchanged rules. | no |
| MOC membership sync (`<!-- klyreon:members -->` block) | redesign | MOCs become bim index notes (`type: index`, `§` title) in the engine folder; marker renamed `<!-- tx:members -->`; members written as wikilinks. | no |
| Pruning, off by default, one grouped commit | redesign | A note linked from outside the engine folder is never a candidate (the engine must not edit private notes, idea hard part 7). | no |
| Scheduler: launchd plist / crontab line, PATH captured, `;` not `&&` | port | Unchanged mechanics; also add a log file path (code-only row below). | no |

### Format (spec sections 3 to 10)

| row | classification | reason | code-only |
|-----|-----------------|--------|-----------|
| Two species: source documents vs zettels | redesign | Source documents leave the vault and live in mirror roots; only zettels stay, as bim notes. | no |
| Source-document `type` vocabulary and type-specific fields (`article-*`, `book-*`, `quote-*`, `transcript-*`) | redesign | Exporters own mirror files and do not write this frontmatter; tx reads whatever metadata the file has and keeps none of it as a rule. | no |
| 14-digit id, collision bump in lockstep | port | bim ids are the same; bump in lockstep with `date`. | no |
| Required `id`, `title`, `created`, `type`; H1 = title | redesign | `created` becomes bim's `date`; key order follows bim; H1 rule unchanged. | no |
| `updated`, `tags`, `publish` (tools write `false` only), `processed`, `reviewed` | port | bim already writes `publish: false`, `processed: false`; `updated`/`reviewed` carry over. | no |
| Concept fields `concept-type`, `assent`, `lifecycle`, `claims`, `doubts` and their closed enums | port | Fit bim frontmatter as nested YAML (round trip measured, idea.md). | no |
| Claims rules (required on thesis/argument/observation, none on aporia, 1 to 3) | port | Unchanged. | no |
| Doubt shape and `target {to, claim}` | redesign | `target.to` becomes a vault-relative note path (`notes/tiromex/...`), not a klyreon-root path. | no |
| `links` (10 relations, transitive-cycle rule) | redesign | One backmatter key per relation: `- supports:: [[notes/tiromex/tx/<id>\|Title]]`. Same closed list and cycle check. | no |
| `sources` field | redesign | Backmatter `- source::` naming a mirror root and a path in it; a root missing on this host is reported "not on this host", never dangling (qa-log). | no |
| `mocs` field | redesign | Backmatter `- parent::` to the index note, bim's existing key. | no |
| `delivered-as` | port | Frontmatter list, unchanged; still exempts from pruning. | no |
| Tags: kebab-case, no colon namespaces | port | Plus: tx never writes `person` or `book` (Auto Note Mover). | no |
| Utility zettels (no concept fields) | port | Same eight types, all already bim types. | no |
| Body shapes (Socratic, utility) | port | Already match bim body shapes. | no |
| Unknown frontmatter keys preserved | port | bim's model already keeps them. | no |
| Operator skill content (vocabularies, claim/doubt rules, conflict shapes) | redesign | Folded into `src/tools/bim/SKILL.md` as a tiromex section, with the exception to the approval rule. | no |
| Docs page `klyreon.rst`, reference docs | redesign | Content moves into `bim.rst` and a revised format spec under `docs/reference/bim/` (or similar); philosophy docs stay as reference. | no |

### Code-only rows

| row | classification | reason | code-only |
|-----|-----------------|--------|-----------|
| Sources sorted by bare filename, cap takes first N, rest "deferred" | port | Sort by mirror root then full path, so the order is stable. | yes |
| Claim set built once per sweep: sources in one run cannot conflict with each other | port | Known limit; rebuild after each committed source is a cheap fix, decided in design. | yes |
| Per-source clock offset of idx*10s (future ids) | drop | Collision bump already guarantees unique ids; the offset only skews `date`. | yes |
| Source must have a `---` fence or it fails | redesign | Exporter files may lack frontmatter; read body with or without it. | yes |
| `--dry-run` copies an outside PATH into the vault | redesign | Dry run writes nothing; nothing is copied at all (mirror files are read in place). | yes |
| Missing PATH raises an uncaught error | port | Return a `CommandResult` failure. | yes |
| Conflict target parse outside try: a bad target aborts the run, no trail | port | Fix in the port: a bad target fails that source only. | yes |
| Backend-returned MOC and `target.to` paths are not confined | port | Fix in the port: confine to the engine folder; this is the write boundary of tiromex. | yes |
| Malformed existing MOC replaced wholesale | port | Fix in the port: report and skip, never discard prose. | yes |
| Ingest commit identity hard-coded, ignores settings | port | Fix in the port: use the settings. | yes |
| Prune commit skips the `GIT_AUTHOR_*` env override | port | Fix in the port: one commit helper for every commit. | yes |
| Own `sources` count as corroboration, so ingested notes are never prune candidates | port | Fix in the port: count only sources other than the note's own. | yes |
| Pruning removes only `target` from doubts naming the pruned note | port | Keep; the doubt stays as a record. | yes |
| `oversized-body` hits source documents and trails | drop | Moot: sources leave the vault; the rule checks only engine notes. | yes |
| Unparseable notes silently left out of the graph | port | Keep; validate reports them. | yes |
| Promotions do not bump `updated` | port | Spec 7.7 behaviour, unchanged. | yes |
| MOC member block sorted by path | port | Unchanged. | yes |
| State `last_maintain` per user, not per vault | port | Keep one clock under `$XDG_STATE_HOME/bim/tx/state.json`; one vault per bim config. | yes |
| Lock file per vault hash, never removed (about 270 stale files in `~/.local/state/klyreon` on 2026-11-15) | redesign | Tests must isolate `XDG_STATE_HOME`; the lock file is reused, not one per temp vault. | yes |
| `is_human_authored` defined but never called | drop | Dead code. | yes |
| `StubBackend` reachable from the CLI, always fails | redesign | Stub stays a test fixture only; not offered as a CLI backend name. | yes |
| claude adapter: `--tools ""`, temp cwd, stdin prompt, timeout plus 30 s, envelope parsing | port | Becomes the `claude` adapter of the shared layer. | yes |
| `BackendError` closed reasons (timeout/exit/parse/schema) | port | Shared layer keeps them. | yes |
| `IngestPayload` schema, `extra=forbid` | redesign | `target.to` and MOC paths change to engine-relative; schema size vs small local models is a measured risk in discovery. | yes |
| Prompt rules the code does not check (claim <= 40 words, banned words, no body links) | port | Kept in the prompt; enforcement stays out of scope. | yes |
| launchd plist discards stdout and stderr | redesign | Log to `~/Library/Logs/bim/tx.log` (macOS) so failed runs leave a record. | yes |
| `status` prints staleness twice; pending count disagrees with ingest | port | Fix in the port: one line; one pending definition. | yes |
| `manifest.toml` command table misses maintain, schedule, assets | drop | klyreon's manifest goes away; bim's manifest gains `tx`. | yes |
| Settings `extra=forbid` | port | bim settings already forbid unknown keys. | yes |

## Drop Rulings

Walked with the owner one by one on 2026-11-15. The port and redesign rows
were approved as one table the same day.

### `klyreon init`, its flags, root config and `$KLYREON_ROOT`

- **Evidence presented**: `~/bim` is a git work tree (checked 2026-11-15);
  `~/.config/klyreon/config.yaml` points at a deleted temp dir; no klyreon
  vault is in use.
- **Ruling**: drop (owner, 2026-11-15)

### `klyreon assets` group (installer, manifest, backups)

- **Evidence presented**: no klyreon skill is installed
  (`~/.claude/skills/klyreon` absent); `bim --skill` already ships a skill.
- **Ruling**: drop (owner, 2026-11-15)

### Per-source clock offset (idx*10s)

- **Evidence presented**: `ingest/pipeline.py:283`; the collision bump in
  `vault/ids.py:40-57` already gives unique ids.
- **Ruling**: drop (owner, 2026-11-15)

### `oversized-body` on sources and trails

- **Evidence presented**: `spec/validator.py:420-424`; sources leave the vault.
- **Ruling**: drop (owner, 2026-11-15)

### `is_human_authored`

- **Evidence presented**: `vault/git.py:141-150`, no caller.
- **Ruling**: drop (owner, 2026-11-15)

### klyreon `manifest.toml`

- **Evidence presented**: `manifest.toml:14-20`; bim's manifest covers bim.
- **Ruling**: drop (owner, 2026-11-15)

## Consumer Cutover

| consumer | current reference | new reference | cutover step |
|----------|--------------------|----------------|---------------|
| `pyproject.toml` entry point | `klyreon = "klyreon.cli:cli"` (line 49) | none | remove in phase 6 |
| `pyproject.toml` wheel packages | `"src/tools/klyreon"` (line 90) | none | remove in phase 6 |
| `pyproject.toml` pytest marker | `klyreon: klyreon tests` (line 118) | `bim` marker covers `tests/tools/bim/tx/` | remove in phase 6 |
| `tools/lib/check_tool_wiring.py` | expects every `src/tools/*` wired | no klyreon dir | passes once dir is gone |
| `docs/source/tools.rst` | lines 47, 130 | `bim` entry mentions `bim tx` | phase 6 |
| `docs/source/tools/klyreon.rst` | whole page | `docs/source/tools/bim.rst` tx section | written in phases 1 to 5, page removed in 6 |
| `docs/reference/klyreon/*.md` | format spec, philosophy docs | revised spec beside bim docs; philosophy docs kept or moved | phase 1 (spec), phase 6 (move rest) |
| `tests/tools/klyreon/` | 5,305 lines of tests | `tests/tools/bim/tx/` | ported per phase, removed in 6 |
| `~/.config/klyreon/config.yaml` | stale temp-dir root | none | delete in phase 6 (hand-off: dotfiles side) |
| `~/.config/buvis/dotfiles-ledger.json` | `.config/klyreon/` entry (line 187) | none | drop entry in phase 6 (dotfiles repo) |
| `~/.local/state/klyreon/` | `state.json` + about 270 lock files | `$XDG_STATE_HOME/bim/tx/` | delete in phase 6 |
| Branch `feature/config-local-layer-braid` | edits `src/tools/klyreon/cli.py` | none | resolve at merge; no klyreon change survives |
| `CHANGELOG.md` | history lines 98, 212-215 | unchanged (history) | none; phase 6 adds a Removed entry |

Searched 2026-11-15: this worktree, `~/git/src/github.com` (only the main gems
checkout hits), `~/.claude/{rules,AGENTS.md,hooks}`, `~/.config`. No skill in
`~/.claude/skills/klyreon`, no `net.buvis.klyreon.plist`. Not searched: repos
outside `~/git/src/github.com`, crontab.

## Phases (dependency order)

Estimate, not measured: six PRDs.

1. **tiromex and the folded format** - no dependencies. Setting for the
   tiromex folder; bim format gains concept fields, backmatter relations and
   index notes; engine model on `pybase.zettel`; `bim tx new`, `validate`,
   `export-claims`, `status`; bim skill exception and tiromex section.
2. **Shared LLM backend layer** - no dependencies. One backend registry in
   bim: local HTTP (Ollama, llama.cpp, OpenAI-compatible) and agent CLIs
   (claude adapter ported, a generic command driver); text in, schema-checked
   JSON out, no file access. `bim doc` classifier and extractor move onto it.
3. **Mirror roots** - no dependencies. Named mirror roots in bim settings
   (machine-local values on the local config layer); `bim create -t article`
   writes into the git mirror; migrate existing `path_articles` originals and
   repoint `article::` links, with `--dry-run`.
4. **`bim tx ingest`** - depends on phases 1, 2 and 3. Mirror reads with hash
   records, conflict shapes, staging, lock, scoped commits, run journal,
   code-only fixes.
5. **`bim tx maintain`, schedule, interfaces** - depends on phase 4. Maintain
   and pruning scoped to the engine folder; schedule; tx actions in the serve
   action registry and TUI per the all-interface rule.
6. **Retire klyreon** - depends on phase 5. Remove the tool, docs, wiring and
   local state; this phase carries the Retirement block below.

Do not start a phase until the phase before it has landed and its exit
criteria hold.

## Retirement

The retirement PRD belongs to buvis/gems (the repo where the code dies), and
is written alongside the final port phase rather than remembered later.

Retire `src/tools/klyreon/` (and `docs/source/tools/klyreon.rst`,
`docs/reference/klyreon/`, `tests/tools/klyreon/`) once every criterion below
holds:

| row | classification | reason | code-only |
|-----|-----------------|--------|-----------|
| (every row of the Inventory Matrix above) | as above | as above | as above |

- [ ] Every row above is classified, and every row with `code-only` = no has
  its test/doc/config follow-up landed.
- [ ] export-claims ports cleanly: `bim tx export-claims` emits
  `{schema_version, generated, claims[]}` for engine-folder notes only, and
  `--out` under the vault root is refused.
- [ ] status ports cleanly: `bim tx status` prints counts by lifecycle and
  assent, links per note, aporias, prune candidates and one maintenance line.
- [ ] maintain ports cleanly: two `bim tx maintain` runs in a row; the second
  changes nothing; `--dry-run` writes nothing.
- [ ] schedule ports cleanly: `bim tx schedule install/status/uninstall`
  round-trips on macOS and Linux in tests with the artifact hash checked.
- [ ] Path confinement ports cleanly: a note or backend path with `..`, an
  absolute path or a symlink escape is rejected.
- [ ] Each tx setting (`max_sources_per_run` ... `prune_window_days`,
  `git_identity_*`) ports cleanly: set in `buvis-bim.yaml` under `tx:`, it
  changes the matching behaviour in a test.
- [ ] Git gate, scoped commits, lock, staging and rollback port cleanly: the
  klyreon tests for each pass against `bim tx`.
- [ ] Lifecycle, assent and MOC sync rules port cleanly: the klyreon fixture
  cases give the same transitions.
- [ ] Format rows (id bump, review fields, concept fields, claims rules,
  `delivered-as`, tags, utility notes, body shapes, unknown keys) port
  cleanly: `bim tx validate` accepts the converted fixtures and rejects each
  broken one with the same rule name.
- [ ] Each code-only `port` row is covered by a regression test that failed
  on the klyreon code.
- [ ] Every consumer listed in the Consumer Cutover table now points at
  `new reference`, and no code still references `current reference`.
- [ ] CI is green on the branch that removes `src/tools/klyreon/`.
- [ ] `rg -i klyreon src tests docs/source pyproject.toml` finds nothing.
