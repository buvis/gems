# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- **deps**: resolved both audited CVEs by upgrading rather than suppressing (PRD 00086). `oauthlib` is floored to `>=4.0.0` via a `[tool.uv]` `constraint-dependencies` entry — it is purely transitive (`jira` → `requests-oauthlib` → `oauthlib`) and its CVE-2026-49265 fix in 4.0.0 has only OAuth2 provider-side breaking changes that gems does not use (the Jira adapter authenticates with server+token, not any OAuth flow). The stale `--ignore-vuln CVE-2026-4539` (pygments, already fixed by 2.21.0 in the lock) is removed from the CI audit step. To keep suppressions from going stale, ignored CVEs now live only in a dated/justified `dev/audit/pip-audit-ignores.toml` (cve, package, reason, date_added) — currently empty — and a deterministic guard (`dev/bin/check_audit_ignores.py`, with tests under `tests/dev/`) both generates pip-audit's ignore flags from that file and fails the build if any listed CVE later gains an available fix in the resolved tree.

### Added

- **postup**: the deterministic brief now raises a **brush-audit cadence nag** — a maintenance todo when a repo's brush report was never generated or is past the 30-day cadence, mirroring the existing purge-trash nag. The derive layer previously defined the brush cadence constant but never consumed it (`brush_last_run` was collected but never surfaced as a todo), so the Python text brief and TUI silently dropped the brush nag that the earlier JS surface showed; this wires it in and covers the never-brushed / at-threshold / within-threshold cases with tests.

- **postup**: the brief now surfaces the **meta-budget share** — Claude-on-Claude ("meta") spend as a percentage of total spend over a trailing window, with a green/red state at an inclusive 30% ceiling, in both the text brief and the web dashboard. A new pure, UI-free `postup.domain.meta_share` collector reads the cost ledger written by `track_cost.py` at `~/.local/share/agents/metrics/costs.jsonl` (ledger dir and transcripts dir are both constructor-overridable, never hardcoded). Ledger rows are **cumulative per session** — a session's spend is the MAX (last-by-`ts`) `cost_usd` for that `sid`, never the sum of its rows — and carry no project/cwd field, so attribution uses a documented **sid→transcript-dir join**: it globs Claude's `~/.claude/projects/<encoded-cwd>/<sid>.jsonl`, and a session whose cwd is at or under `~/.claude` counts as **meta** while every other cwd — and any session with no locatable transcript — counts as **product**, so the meta share is never silently inflated. An absent or empty ledger (for the window) renders **"meta n/a"**, never an error. The share is a `MetaShare` typed model added optionally and additively to the `PortfolioData` contract (no `schema_version` bump); the text brief (`postup` / `postup brief`) computes it fresh from the live ledger at render time, and `postup collect` snapshots it into `data.json` so the web tile reads the collected contract. The web frontend gains a **Meta budget** tile on the Brief consuming `MetaShare` through the existing payload seam, with the same green/under-ceiling, red/over-ceiling, and n/a states. Covered by domain unit tests (meta/product/no-transcript attribution, cumulative-per-sid max-not-sum, empty ledger → n/a, a fixture ledger reproducing a known 25%, the inclusive 30.0% → red boundary, and window filtering — all against fixture ledger + transcript roots, never the real `~/.local`/`~/.claude`), a text-brief render test (percentage + state, and n/a), and a Svelte component test for the tile.

- **postup**: `postup collect` now tracks the migrated `docs/dev/project-management/` project-management layout, keeping it a faithful superset of the `brief-portfolio` skill after that skill's path migration. The PRD-pipeline and brush-report readers prefer the migrated `docs/dev/project-management/{prds,audit-results/brush-report.md}` locations and fall back to the legacy `dev/local/` locations (a mid-migration repo reads the migrated one), so both migrated and not-yet-migrated repos report correctly. A new **purge/trash cadence** signal is read — `purge_last_run`, the newest dated (`YYYY-MM-DD`) subdirectory name under `docs/dev/tmp/.trash` (legacy fallback `dev/local/.trash`), a name-based signal — added to the `RepoData` contract (additive, no schema bump), wired into `postup collect`, and surfaced by the derive layer as a maintenance nag when the trash was never purged or the cadence is overdue, mirroring the brush cadence. All new reads stay pure-filesystem in the domain layer (interface-agnostic invariant).

- **postup**: new `postup serve` command — a FastAPI + SSE web server that delivers the SvelteKit brief UI (built in 00065/00066) over localhost, following bim's serve pattern. It serves the committed production build from `src/tools/postup/adapters/web/frontend/build/` and exposes the exact `/api` endpoints the frontend prod loader fetches: `GET /api/data`, `/api/epics`, `/api/data-prev`, and `/api/history`. It **serves the last collected data until refreshed** — it never auto-collects on start (no startup latency or surprise network calls; the UI has a collect trigger + live SSE) and a never-collected `out_dir` returns an **explicit empty-portfolio state** (`repos: []`, HTTP 200), not a 500. `GET /api/events` streams Server-Sent Events: a `watchfiles` watcher over `out_dir` pushes a single `file_change` event per logical refresh so the browser re-fetches without a manual reload, and the collector's atomic-replace write (00063) coalesces into exactly one event rather than a storm. `POST /api/actions/collect` and `/api/actions/enrich` trigger a run from the UI by driving the **same command classes as the CLI** (`CommandCollect` / `CommandEnrich`) through the composition root (the all-interface rule — no business logic reimplemented in routes); a concurrent trigger while a run is active is rejected with an *already running* status (HTTP 409) rather than launching a second run. The 00042 confinement posture is applied from day one: localhost bind, `TrustedHostMiddleware` (non-loopback Host headers rejected), a per-process auth token guarding the mutating trigger routes (injected into `index.html` on loopback), and every request-derived filesystem path `resolve()`d and asserted under `out_dir` before any read. `CommandServe` returns a `CommandResult` for every outcome and never raises or exits; fastapi/uvicorn/watchfiles are optional dependencies behind a new **`postup-web`** extra (mirroring `bim-web`, and added to `all`), and a missing extra yields a `console.require_import()` install hint rather than a traceback. The wheel build hook (`hatch_build.py`) is generalized to build and package **both** tool frontends (bim and postup) for release wheels, honoring `BUVIS_SKIP_FRONTEND`, with a build-hook test covering both tool dirs.

- **postup**: web frontend feature parity — the four remaining tabs, the per-repo drill-down, and the temporal features, completing the SvelteKit rebuild started in 00065. New routes: **Matrix** (solo-dev Eisenhower quadrants from the merged todo set; when `epics.json` is absent it degrades to a mechanical-todo list with a *not enriched* cue), **Activity** (per-repo commit-heat grid + recent releases, with each repo's `errors[]` surfaced as an inline collection-warning badge rather than a silent gap), **Work** (in-flight work grouped by repo — local dirty/ahead-behind/stash state, stray branches/worktrees, open PRs — plus portfolio-external review-requested/authored PRs, and a *clean* empty state instead of a blank page), **PRDs** (per-repo `backlog`/`wip`/`done` pipeline counts, omitting repos with no `dev/local/prds` tree rather than zero-filling them), and **`/repo/[owner/name]`** (a `RepoDetail` drill-down reachable from Repos/Activity/Work that renders one repo's full slice with its `errors[]` shown VERBATIM). Temporal features land on the Brief: an **Attention Horizon** strip presenting the derive layer's ranked attention queue, **since-last diff** badges (Brief + Repos) computed against the rotated `data-prev.json` (first run with no prev renders no markers), and a **trend sparkline** from `history.jsonl` (a single history line renders as a dot, not an error). The `derive` layer gains the PRD-named temporal functions test-first — `diffSinceLast`, `trendSeries`, `attentionHorizon`, plus the `weekStart`/`monthLabels` commit-heat helpers — and the payload loader now also loads `data-prev.json` and parses `history.jsonl` (tolerant of a torn tail) in both dev-fixture and prod-`/api` modes. Every view ships a Svelte **component test** (mounted via `@testing-library/svelte` + `jsdom`, added as test-only dev-deps with the toolchain pins untouched), covering the Matrix deterministic fallback, the Work empty state, RepoDetail's verbatim errors, and the temporal with-prev/without-prev/thin-history cases; the committed production build is refreshed. A per-component SPA parity sweep is recorded under `dev/local/audit-results/`.
- **postup**: new web frontend core — a SvelteKit SPA rebuild of the portfolio brief, mirroring bim's frontend subtree convention (static adapter, no SSR, same toolchain pins) at `src/tools/postup/adapters/web/frontend/`. Lands the app skeleton, the ported pure-logic `derive` layer (ported tests first, then wired), a single payload-loader seam, and the first three tabs — **Brief**, **Todos**, **Repos** (the rest are 00066). The `derive` layer is a framework-free parity port of the old brief-portfolio SPA's only tested module (attention scoring with human-readable reasons, mechanical todos, external PRs, since-last diff, quick wins), with its localStorage done-state moved to a `postup-`namespaced key and pruned to the current payload's ids. Views never read files or URLs themselves: the loader is the one seam — in dev it loads committed fixtures (a missing `epics.json` renders the deterministic, *not enriched* subset; a missing `data.json` renders a *run postup collect first* cue), and in prod it fetches from the future `postup serve` (00067) `/api` endpoints. The fixtures are byte-generated from the Python `data.json` contract, and a **JS↔Python derive parity test** — the seam PRD 00068 deferred — asserts the same fixture yields the same derived view-model (per-repo summaries, ranked attention queue, mechanical + judgment todos, portfolio errors) on both sides. The production build is committed (so 00067 can serve it without a node toolchain — unlike bim, which builds on-demand); vitest is the JS test harness (`npm test`), not part of the pytest CI gate (`BUVIS_SKIP_FRONTEND`). (`postup.domain.derive`) so the two surfaces render identical facts for the same `data.json` (the all-interface rule). The derive layer folds `data.json` + optional `data-prev.json` + optional `epics.json` into a typed, UI-free view-model (attention queue, mechanical todos, per-repo summary, since-last diff); a missing `epics.json` yields the deterministic subset with a *not enriched* cue, and a missing `data.json` yields a *run postup collect first* state rather than an exception. The text brief is the default surface and imports **no Textual** on that path (enforced by an import-isolation test, not convention), so it runs on the core-only install; `postup tui` needs the new `postup` extra (Textual) and reports a standardized install hint via `console.require_import()` when the extra is absent — never a traceback. The Textual layout is covered by snapshot tests (main, degraded `errors[]`, and not-enriched states) that run only on the canonical CI env and auto-skip elsewhere. The JS/Python derive parity test is deferred until the JS derive (00065) exists; the Python derive owns the canonical fixture payloads until then.
- **postup**: new `postup enrich` command — an optional LLM step that shells out to the `claude` CLI (`claude -p`, the only LLM path; no cloud SDK, no new dependency) to add the model-authored portion of the brief on top of the deterministic `postup collect` output. It detects `claude` on `PATH` before building anything and alerts which mode/model will run; when `claude` is absent it warns that narrative/epics/judgment-todos will be missing, continues deterministically, and still exits successfully — enrichment never blocks the brief. It reads `data.json` + `commits-digest.md`, builds a versioned prompt owned by the gem (ported from the old brief-portfolio skill, with the commit digest treated as untrusted data), invokes `claude`, and validates the response against a new `EpicsPayload` pydantic schema (portfolio `summary`, per-repo `epics` with exact commit `shas`, and judgment `todos` with `urgency`/`importance`/`effort`). Every epic SHA is cross-checked against the collected commit set so a hallucinated reference is rejected, and each todo id is recomputed deterministically from `(repo, action)` so done-state survives re-enrichment. On a parse/validation failure it retries exactly once with the errors appended to the prompt; a second failure warns and continues without writing a partial file. `epics.json` is written atomically (`pybase.filesystem.atomic_write`). The `model` setting is passed to `claude` only when set — otherwise the CLI's own default model is used (postup pins nothing). A large portfolio's digest is capped per-repo (largest repos trimmed first, each repo kept present) rather than chunked, so enrichment stays a single coherent call. A missing `data.json` is the one hard failure: the command tells the user to run `postup collect` first.
- **postup**: new gem — **PO**rtfolio **ST**and**UP**, scaffolded as the first four-interface gem (cli/tui/rest/web in its manifest; CLI implemented here, the rest land in later PRDs). Ships `postup collect`: a deterministic, LLM-free portfolio collector. It discovers repositories by scanning settings-defined `roots` for `.git` (minus an `excludes` list; no `gita` dependency), then gathers each repo's signals in a bounded thread pool via local `git` and an authenticated `gh` CLI — commits/releases/last-tag/unreleased, open issues and PRs, CI runs, security alerts, stray branches and worktrees, the `dev/local/prds` pipeline counts, CHANGELOG `[Unreleased]` state, brush-hygiene recency, local branch/dirty/ahead-behind/stashes, and portfolio-external review-requested/authored PRs. A per-repo failure (`gh` unauthenticated, network, odd repo state) degrades into that repo's `errors[]` and a console warning — the run never crashes and exits successfully. Outputs are four atomically-written (`pybase.filesystem.atomic_write`) file contracts under `out_dir` (XDG `~/.local/share/postup` by default): a typed, versioned `data.json` (`schema_version`, unknown version rejected loudly on read), `commits-digest.md`, a `data-prev.json` rotated **before** the new snapshot lands, and an appended `history.jsonl` trend line. `--no-fetch` skips the remote refresh and `--days` narrows the commit window. Zero new runtime dependencies — it runs on the core-only install. `PostupSettings` layers CLI > env (`BUVIS_POSTUP_`) > YAML config > defaults.
- **bim**: new `bim doc triage` review surface. `bim doc triage` lists pending `*.proposed.yml` proposals under `<business_root>/_triage/` (issuer, doc type, date, triage reasons, path); `bim doc triage --approve <id-or-path>` sets `approved: true` and promotes the proposal through the existing collision-safe promote path — replacing the manual "edit the YAML, then run `bim doc promote`" flow. Both verbs are registered in the `bim serve` action registry (`triage_list`, `triage_approve`) and reachable through the generic `POST /api/actions/{name}` route, so the WebUI drives the same command classes as the CLI (200 on success, 422 + envelope on failure). `triage_approve` confines its proposal path in two stages: the shared request allow-list (vault, archive, and now `<business_root>/_triage/`), then a narrowing check that the resolved path lies **under `<business_root>/_triage/` specifically** — a `.proposed.yml` placed elsewhere in the vault or archive, or an unconfigured triage root, is refused with HTTP 403. The broader `bim serve` token/TrustedHost rework (00042) is intentionally out of scope. `httpx` is added to the test dependency group so the serve `TestClient` suite actually runs.
- **bim**: new `bim doc migrate-layout` command finishes the migration promised by `bim doc audit`'s `legacy_layout_zettels` list — it moves each legacy flat-layout document zettel (`<vault>/<doc-subdir>/<basename>.md`) into its per-issuer subfolder (`<vault>/<doc-subdir>/<issuer-slug>/<basename>.md`), reading the issuer slug from the zettel's own `file-path` link. Dry-run by default (prints the plan, changes nothing); `--apply` performs the moves atomically (write per-issuer copy, then drop the legacy file). A zettel with unparseable frontmatter, a missing `file-path`, or a pre-existing target is skipped and reported — never partially migrated. After a successful apply, a re-run of `bim doc audit` shows those zettels are no longer legacy.
- **backup**: `--source PATH` / `--out PATH` override the single selected instance's source / out for a one-shot run (flag wins over config); requires exactly one instance selected via `--only`, and erroring via `console` when more than one is selected rather than silently picking one. With no override flags the run is byte-identical to before.
- **backup**: `--show-excludes <instance> --for <path>` prints, read-only (writing no archive), the instance's resolved global exclude set (already post-`excludes+` / `excludes-`) and the `.bkpignore` add / `!`-unignore rules effective under `<path>`, resolved with the same layering the archive walk uses. Without `--for` it prints the global set only and notes that path-dependent `.bkpignore` rules are omitted.
- **backup**: `tar-archive` gains an opt-in `engine: system-tar` input (default `python-tarfile`) that keeps file selection and `.bkpignore` scoping in Python but hands the exact include list to system `tar -T` for speed on large trees, preserving the `chmod 600` atomic-replace guarantee; a missing or failing `tar` falls back to the Python engine and notes the fallback in the step result. Default / unset engine is byte-identical to before.
- **backup**: new gem — a config-driven archiver that runs configured capabilities, mirroring sysup's pattern (own `config.py`, `runner.py`, `capabilities/`, `cli.py`, `default.yaml`) while sharing no code with it. Ships one `tar-archive` capability: it `os.walk`s a source tree, filters each path against a composed exclude set, and streams the survivors into a `chmod 600`, atomically-written (`tempfile` + `fsync` + `os.replace`) `.tar.gz`. git-src ships as a config instance reproducing the former `backup-git` script (`~/git/src` → timestamped `~/.local/backup/git-src-*.tar.gz`, same 32 excludes). Global excludes ship as a plain `excludes:` list and layer via `excludes+` / `excludes-` across gem → user → machine config; a per-repo `.bkpignore` (gitignore-style) adds a repo-local exclude with a bare line and cancels an inherited default with `!pattern`, both path-scoped to that file's subtree. CLI is `--only` / `--tag` / `--list` / `--dry-run` plus `buvis_options`; `--dry-run` reports the resolved out-path, file count, total bytes, and applied `.bkpignore` rules while writing nothing.
- **pybase**: config merge now supports list directives. A key suffixed `+` appends to its list-valued base key (order-preserving, dedup) and a key suffixed `-` removes from it, so a lower layer can extend or trim a shared list without re-listing it — e.g. `excludes+: [foo]`. Within one layer a plain `key` resets the list first, then same-layer `+`/`-` apply (append before remove, so removal wins). Directive keys are stripped from the merged result. `merge_configs` gains an optional `known_keys` set that warns when a directive targets an unknown base key (a cheap typo guard). A directive on a non-list key raises `ConfigurationError`.
- **sysup**: updaters are now defined in configuration (`buvis-sysup.yaml` in the buvis config stack), not code. Entries are a flat map keyed by name, deep-merged over a bundled default, so a machine can add, reorder, or disable (`enabled: false`) an updater without editing Python. A sibling `buvis-sysup.local.yaml` (never `dot add`ed) overrides shared values per machine. Each entry is either a `run` entry (a list of argv arrays, no shell) or a `use` entry naming a built-in capability (`helm-repo-update`, `nvim-mason`, `pip-outdated`, `sudo-prime`) with optional `with:` inputs. `sysup --list` prints the resolved plan for the host and `sysup --dry-run` shows what would run without running it.

### Changed

- **postup**: postup is now the portfolio-brief implementation of record — it supersedes the standalone `brief-portfolio` Claude skill (PRD 00070 cutover). A data-level parity gate (`dev/bin/parity_brief_portfolio.py` + `tests/tools/postup/test_parity.py`) proves postup's collector covers every per-repo signal field the skill's collector produces over the same gita-derived portfolio snapshot, and blocks the cutover if any field the skill emits is absent from postup; enrichment is compared structurally (a schema-valid `epics.json` exists) and narrative/epic content is excluded. The 2026-09-29 real-portfolio run recorded full coverage across all 25 collected repos. The skill's actual deletion is an owner action outside gems (documented in the PRD completion notes); postup's trend/diff history restarts fresh with no migration of the skill's history.
- **dot**: the diff pane's viewport math (hunk→line-offset map, index/line/selection clamping, and scroll-reveal target) is extracted into a pure `DiffLayout` model (`dot.tui.widgets.diff_layout`, no Textual dependency); `DiffView` is now a thin renderer that asks `DiffLayout` where things are and holds no inline offset arithmetic. Behaviour is unchanged — the coordinate math is now unit-tested without a TUI, covering every edge that previously shipped as a scroll/offset bug (headerless diff, single hunk, reveal past the last hunk, clamp at both ends, empty diff).
- **sysup**: the `mac`, `pip`, `nvim`, and `wsl` subcommands (and their `sys.platform` guards) are removed. `sysup` with no argument now runs every updater whose `when` guard matches the host, in order; `--only <names>` and `--tag <t>` narrow the run. With no user config the behaviour is unchanged — on macOS `sysup` runs the former `sysup mac` steps (brew → npm-check → pip → uv → helm → mise, mise last among the tool managers) and on Linux the former `sysup wsl` steps (apt → snap), now host-selected by each entry's `when` instead of a subcommand. The former standalone `sysup nvim` (headless Mason update) is also restored to the default plan as a cross-platform `use: nvim-mason` entry that runs after mise wherever nvim resolves.

### Removed

- **hello-world**: the sample `hello-world` tool is gone, and with it the `hello-world` console script and the `hello-world` optional-dependency extra (`pyfiglet`). New tools are scaffolded from `dev/bin/scaffold.py`, which never depended on it.
- **pidash**: the autopilot-dashboard TUI is retired from gems (tool, tests, docs page, console script, `pidash` extra and its membership in `all`, pytest marker). Its function moved to `tracon` in the buvis home repo, next to the autopilot state schema it reads; no gems-side replacement ships.
- **pybase**: the unused `UvAdapter` / `UvToolManager` uv adapter is removed (superseded by the updater subsystem); it had no production or out-of-repo consumers.
- **pybase**: the `configuration/examples` sample settings (`MusicSettings`, `PhotoSettings`) are removed; they were consumed only by their own tests.
- **pybase**: the dead `StringOperator` surface is pruned — `slugify`, `prepend`, `humanize`, `as_graphql_field_name`, and all word-level singularize/pluralize helpers had no production callers and are gone. The six live helpers (`collapse`, `shorten`, `underscore`, `as_note_field_name`, `camelize`, `replace_abbreviations`) are kept. The `suggest_tags` Ollama client moved out of `formatting` into `bim` (`bim/shared/suggest_tags.py`), its only consumer, so the bottom-layer formatting package no longer imports `console` or `urllib`.

### Fixed

- **dot** (and **pybase**): shell quoting now holds end to end. `ShellAdapter` (pybase) no longer runs `os.path.expandvars` over the whole command — expansion is confined to the registered alias body — so a `$VAR` inside a caller's `shlex.quote`d argument can no longer be expanded back inside its own quotes (which defeated quoting at every call site and allowed injection via a crafted filename such as `my$EVIL file`). `dot delete` now `shlex.quote`s its path in both the plaintext (`cfg rm`) and encrypted (`cfg secret remove -c`) branches, which were previously interpolated raw. Both `dot rm` and `dot delete` now pass `--` before the pathspec so a file named `-c`, `-f`, or `--force` is treated as a path, not a flag.
- **dot**: `dot`'s secret registration now also passes `--` before the path — `DotGitService.register_secret` / `unregister_secret` / `encrypt_and_stage` emit `cfg secret add -- <path>` / `cfg secret remove -- <path>` — so a secret whose filename begins with a dash (`-c`, `-f`) is treated as a pathspec by git-secret's option parser rather than as a flag. `encrypt_and_stage` (the `dot encrypt` path) additionally now `shlex.quote`s its path in both the `cfg secret add` and `cfg add <path>.secret` steps, which were previously interpolated raw. Completes the `--` guard started for `rm`/`delete`.
- **pybase**: `--config FILE` / `--config-dir DIR` now select both the settings source and the tool's own config plan. The `buvis_options` wrapper publishes the resolved selection on the Click context (additive — existing readers are untouched), and `ConfigurationLoader.find_config_files_ranked` accepts an explicit `config_path`. An explicit `--config FILE` is exclusive — it is the sole config layer and directory discovery is skipped, matching the settings resolver so a tool's plan and its settings resolve from the same single file (a discovered user config no longer leaks into the plan under `--config`).
- **backup**: `backup --config FILE` now runs the backup plan from FILE (and `--config-dir DIR` discovers it under DIR), instead of resolving `BackupSettings` from the selection while silently running the default plan.
- **sysup**: `sysup --config FILE` / `--config-dir DIR` now likewise select the updater plan, not just the settings, closing the same latent split.
- **backup**: the `system-tar` engine now passes the include list to `tar` NUL-delimited (`--null -T -`), so a filename containing a newline can no longer split into an extra line and inject an outside or absolute path into the archive. Both engines now produce identical member sets for such names.
- **backup**: `.bkpignore` rules now follow gitignore precedence — a descendant directory's rule overrides an ancestor's, so a repo that re-includes `target/` with `!target` can still exclude a nested `target/` again, and a later line within one `.bkpignore` beats an earlier one. Previously an ancestor un-ignore won permanently.
- **backup**: an unknown `tar-archive` `engine` value is now rejected with a clear error instead of silently falling back to the Python engine (so a typo like `system_tar` no longer looks like it succeeded).
- **backup**: a dry-run and a real run now report the same `total_bytes` (uncompressed input bytes); the compressed on-disk size appears only in the step message, no longer overloading the same field with two meanings.
- **backup**: the `system-tar` engine now `fsync`s its temporary archive before the atomic replace, matching the Python engine's durability guarantee.
- **backup**: malformed YAML, a merge/directive error, a missing required env var, or an unreadable / non-UTF-8 config file (bundled default or user config) now surfaces as a clean fatal error naming the file, instead of an uncaught traceback.
- **backup**: `--show-excludes --for <path>` no longer applies the source-root `.bkpignore` to a path outside the instance source; such a path now resolves to the global excludes only.
- **backup**: the bundled default config now expands `${HOME}` (it is loaded through the same environment-substituting loader as user config), so the zero-config `backup` no longer looks for a literal `${HOME}/git/src` and reports "source not found".
- **backup**: `backup` now exits non-zero when any archive step fails (missing source, invalid engine, permission error, or a caught archive exception), after still rendering every step — so cron and other automation no longer treat an incomplete backup as success.
- **backup**: an `out` path inside the backup `source` is now rejected before walking, so a repeated run can no longer embed the previous archive into the new one and grow recursively.
- **backup**: an unreadable directory in the source tree now fails the backup instead of being silently omitted from an otherwise "successful" archive (`os.walk` errors and per-file `stat` errors propagate to a failed step).
- **backup**: a `source` containing `.` or `..` is now normalized lexically before walking, so a path like `parent/child/..` can no longer produce unsafe `..`-prefixed archive member names.
- **backup**: a shared `config.yaml` / `buvis.yaml` carrying global fields (e.g. `debug`, `log_level`) no longer makes `backup` fail configuration validation — only backup's own top-level keys (`instances`, `excludes`) are read from the merged config, while backup-specific directives like `excludes+` still apply. A misspelled key in a backup-specific file (`buvis-backup*.yaml`, e.g. `instnaces:` or `exclude:`) is still rejected with a clear error rather than silently ignored.
- **backup**: directories are now archived as non-recursive members (the source root and every surviving subdirectory, including empty ones), matching the former `tar -C ... source`, so an empty directory — and an empty source tree's own top-level entry — no longer disappears on restore. The reported file count still counts only regular files.
- **backup**: symlinks are now archived as the link itself (not followed), matching the former `tar` backup, so restoring an archive preserves both file and directory links; directory symlinks are still not descended and their `.bkpignore` is not read.
- **backup**: `.bkpignore` handling now resolves symlinks and stays inside the source tree — a symlink inside the source pointing outside it can no longer cause `.bkpignore` files outside the source to be read and applied, whether via `--show-excludes --for`, a directory symlink encountered during the archive walk, or a symlinked `.bkpignore` file itself.
- **backup**: `--for` supplied without `--show-excludes` is now rejected instead of being silently ignored while a backup runs, so a read-only inspection attempt can no longer create an archive unexpectedly.
- **backup**: `--show-excludes` with an unknown instance (or an instance with no configured source) now exits non-zero instead of 0, so a typo is distinguishable from a successful inspection.
- **backup**: an unknown `--only` name now makes the run exit non-zero (valid names still run), so a mistyped selector can no longer let a scheduled backup silently do nothing; the `--source`/`--out` "exactly one instance" usage error also now exits non-zero.
- **backup**: `--show-excludes --for <path>` no longer reports `.bkpignore` rules from a directory the archive walk would prune (an excluded directory on the path), so introspection matches what the backup actually archives.

## [0.13.0] - 2026-08-17

### Added

- **pybase**: `atomic_write_text` / `atomic_write_bytes` — new public helpers in `buvis.pybase.filesystem` for crash-safe (tempfile + fsync + `os.replace`) writes.
- **bim**: `doc` gains a `claim_max_age_minutes` setting (default 60, a whole number of minutes, rejects zero or less). An ingest claim left behind by a run that died without cleaning up is treated as abandoned once it passes that age, so re-running the document proceeds instead of reporting it as a duplicate forever. The reclaim is a compare-and-delete that never removes a live claim another run legitimately took over in the meantime, and it tolerates a corrupt or unreadable stored `claimed_at` timestamp (including one stored as a BLOB) by treating the claim as abandoned instead of crashing the run.
- **bim**: `doc ingest` now recognises a resent copy of a document that is still awaiting triage review in `_triage/` as a duplicate, instead of re-running the whole pipeline on it. The duplicate sidecar and the recorded dedup entry name it as pending review rather than as an already-filed document.

### Changed

- **bim**: `serve` action and PATCH endpoints now answer with the command's own result envelope and a matching HTTP status — 200 when it succeeded, 422 when it failed — instead of always answering 200 with a hand-built `{"status": "error"}` body. Anything reading these endpoints sees the real outcome, including the warnings the old shape dropped.

### Security

- **bim**: `serve` confines every request-derived filesystem path to the configured vault and archive directories, so its API can no longer read, overwrite, delete, open, or import files outside them. Paths outside the vault are rejected with 403.
- **bim**: `serve` requires a per-run auth token (`X-Buvis-Token`) on its mutating and query-executing routes, and installs a Host allowlist so a web page cannot reach the default loopback-bound server by DNS rebinding. The WebUI sends the token automatically; read-only `GET` routes stay token-free.
- **bim**: `serve` no longer embeds the auth token in the page it serves when bound to a non-loopback host, so a LAN caller (or a DNS-rebinding page) can no longer read the token and gain write access; the token is printed to the operator's console instead.
- **dot**: `rm` now shell-quotes the filename instead of interpolating it raw, so a dotfile name containing a space, `;` or a backtick is passed through literally instead of running as shell. This is necessary but not yet sufficient: the shell adapter still expands `$VAR` and `${VAR}` after the quoting is applied, so a name containing one is still mis-handled — that half is not fixed here.

### Fixed

- **pybase**: config-file precedence is now correct — a tool-specific `buvis-<tool>.yaml` overrides the generic `buvis.yaml`/`config.yaml`, and `$BUVIS_CONFIG_DIR` overrides `~/.config/buvis`. The resolver previously reversed a mixed-order file list, silently inverting both precedences so the generic file won and the override directory lost. Only machines with more than one config file setting the same key were affected.
- **bim**: the WebUI now shows the real reason an action failed instead of reporting it as done — a failed archive, delete, format, sync, import, create, or open surfaces the server's own error text.
- **bim**: the WebUI now treats an error HTTP response as a failure even when its body claims success, so a save can no longer appear to succeed on a 4xx/5xx reply. It also announces a failed "open" to screen readers instead of showing the error only visually.
- **bim**: the TUI now reports a failed create, edit, archive, delete, or format as an error notification instead of showing nothing, or a success-looking message, when the command failed.
- **bim**: creating a note from the TUI now runs the same required-answer validation and default-filling as `bim create` does, so a blank required answer is rejected instead of producing a note with empty fields.
- **fctracker**: transactions are now rejected with a clear error when the CSV is not newest-first, instead of being silently processed in the wrong order and reporting wrong cost basis and rates. The error now names the offending row by the data row number as it appears in the file (header excluded, first data row = 1), instead of an internal reversed-list index that pointed at the wrong row.
- **fctracker**: an overdrawn account, a zero-amount withdrawal, a malformed amount cell, or a non-newest-first CSV now returns a friendly error naming the account, instead of crashing with a raw traceback (`balance`) or a blank/garbled cause (`transactions`). A malformed amount cell now names the offending value and a zero-amount cell says so explicitly, instead of both collapsing into the same generic message.
- **fctracker**: a structurally broken CSV — a ragged/short row, a missing `date`, `amount`, `rate`, or `description` column, or a malformed `rate` cell — now returns a friendly error naming the account, file, and offending row or column, instead of crashing with a raw `TypeError`/`KeyError` traceback. A malformed `rate` cell now names the offending value and says `rate`, instead of being reported as a malformed amount. A ragged row missing only its `rate` cell is now reported as a missing value rather than as a malformed one. A CSV with a UTF-8 BOM header is now read correctly instead of failing on a missing `date` column, and a non-UTF-8 file now names the file and says it is not valid UTF-8 instead of a bare codec message.
- **bim**: `serve` returns 404 instead of crashing with a 500 when its static directory has no `index.html`, and warns instead of silently dropping the auth token when the served page has no `</head>`.
- **bim**: `serve` answers a request whose auth-token header contains a non-ASCII character with the documented 401 instead of crashing into a 500 with a raw stack trace.
- **bim**: `serve` path confinement expands `~` in both the request path and the configured vault/archive directories, so a tilde-form directory no longer locks out every legitimate path with a 403.
- **bim**: `import` writes the imported note atomically, so an interrupted import (crash, kill, disk full) no longer truncates an existing note.
- **pybase**: atomic writes clean up their temp file when interrupted by Ctrl-C, no longer leak a file descriptor if the permission step fails, and no longer replace the real write error with a cleanup error.
- **zettel**: note saves are now atomic — the single write path behind `bim edit`, note creation, archive, the TUI, and the WebUI's action endpoint; an interrupted save no longer truncates the note.
- **bim**: `sync`, `format`, and the WebUI's PATCH endpoint now write notes atomically instead of each using their own bare write, so an interrupted write no longer truncates them.
- **pybase**: updater state is now written atomically, so an interrupted update can no longer leave the shared state JSON torn.
- **bim**: `doc promote` no longer overwrites an already-filed document and its zettel when a second document resolves to the same canonical filename — it files the newcomer under the next free name, and fails without writing anything if no free name is available.
- **bim**: `doc promote` reports a filesystem failure while picking the filed name (read-only vault, permissions, disk full) as a plain error message instead of crashing with a stack trace.
- **bim**: interrupting a `doc ingest` with Ctrl-C no longer parks the document permanently. The claim is released on every exit path, so a re-run proceeds instead of reporting the document as a duplicate that never gets filed.
- **bim**: a document filed through `doc` triage and then `doc promote` is now recognised as a duplicate when the same source arrives again (a re-download or re-export), instead of re-running the whole pipeline and filing a second archive copy under an incremented name.
- **dot**: `rm` on an encrypted (git-secret) file now only untracks it, matching the plain `rm --cached` path — it no longer also deletes the decrypted plaintext copy from disk. The plaintext keeps its `.gitignore` entry, so the surviving cleartext secret is not offered for staging by the next `dot add`, and the committed `<file>.secret` ciphertext is untracked too, so the file really does leave the repo. If untracking the ciphertext fails, the error now says the git-secret mapping was already changed and names the command that restores it, instead of leaving a blind retry to silently take the plaintext path.
- **dot**: the TUI now shows a changed git-secret file in its unstaged pane on first render, instead of only after a prior CLI `dot status` call has hidden it. A failure while hiding secrets no longer leaves the displayed status stale — the file panes still populate and the failure is surfaced in the status bar, where it stays visible until the next refresh instead of being buried by the next keystroke (#92).
- **pybase**: the updater now reports a re-exec failure after a successful upgrade and exits with status 1, instead of exiting 0 silently and leaving the user unaware the restart failed.
- **pybase**: a user-initiated `--update` upgrade is no longer killed after 120 seconds; it now runs for up to 30 minutes before being reported as timed out.
- **zettel**: `find_all` no longer silently drops a note that fails to parse — it returns the remaining notes and prints one warning naming the file(s) that failed. The Python fallback now isolates an unparseable note and reports it instead of crashing the whole scan, and the parse errors the Rust scanner already returned are no longer discarded by the caller.
- **pybase**: updater messages (`--update`, interactive upgrade) now print through the console adapter's styled success/failure/info output on stdout, instead of `click.echo`, some of it previously on stderr.

## [0.12.6] - 2026-08-06

### Security

- **deps**: bump `cryptography` 49.0.0 -> 50.0.0 (PYSEC-2026-3552), pulled in by `pdfminer.six`.

## [0.12.5] - 2026-08-06

### Fixed

- **gems**: publish a source distribution alongside the wheels, so package indexes that list versions from `.tar.gz` filenames (Artifactory mirrors, mise's `pipx` backend) can see new releases.

## [0.12.4] - 2026-08-02

### Added

- **morph**: `morph pdf2png` command — renders every page of a PDF into one tall stacked PNG (poppler `pdftoppm` + Pillow).

## [0.12.3] - 2026-07-19

### Fixed

- **sysup**: `sysup mac` no longer reports a failed helm step on machines with no helm repositories configured — an empty `helm repo list` now reports "no helm repos configured, skipping" instead of helm's "no repositories found" error.

## [0.12.2] - 2026-07-19

### Added

- **sysup**: `sysup mac` caches sudo credentials upfront (`sudo -v` plus a background refresh) so brew cask installs no longer stop for a password mid-run; the prompt now appears once, predictably, at the start.

## [0.12.1] - 2026-07-19

### Fixed

- **deps**: bump `cryptography`, `idna`, `msgpack`, `pillow`, `pip`, `pydantic-settings`, `soupsieve`, `starlette` to patched versions, closing 20 known CVEs flagged by `pip-audit`.
- **sysup**: `sysup nvim` no longer crashes with a raw traceback when a concurrent `mise upgrade` replaces the nvim binary mid-run — the path is re-resolved before each step and a vanished binary reports a failed step instead. Terminal escape sequences are also stripped from the mason timeout message.
- **sysup**: the pip step now upgrades every mise-managed Python (PATH `python3` as fallback) instead of sysup's own interpreter — under a mise pipx install that venv is uv-built and has no pip, so `sysup mac`/`sysup pip` always failed with "No module named pip". Interpreters without pip are reported and skipped.
- **sysup**: `sysup mac` runs `mise upgrade` last. Running it early deleted replaced tool version directories still referenced by the shell's PATH, making later steps falsely report `uv not found` / `helm not found`.

## [0.12.0] - 2026-05-11

### Added

- **pidash**: bundled hook runtime (``pidash hooks run <event>``) plus ``pidash hooks install``/``uninstall``/``status`` admin commands. Run ``pidash hooks install`` after ``pip install buvis-gems[pidash]`` to wire the autopilot dashboard hooks into ``~/.claude/settings.json`` in one step. Existing legacy entries (``python3 ~/.claude/hooks/<name>.py`` paths from the dotfiles repo) are detected and replaced during install, with unrelated hook entries preserved in place.
- **bim**: `bim doc audit` command — read-only walk of the Business folder reporting drift between filed PDFs and zettels. Checks per spec §9: filename canonical, issuer registered, doc-type valid, per-issuer zettel exists, OCR present, sha256 in state.db. Plus rule-engine checks: registry loadability, priority conflicts, freshness (90-day default). Writes a structured JSON report to `<state_dir>/audit/<iso-timestamp>.json`; the report's `legacy_layout_zettels` array is the input contract for the future migration command.

### Fixed

- **pidash**: `pidash hooks install` now fails with a clear error and leaves `settings.json` untouched when the existing `hooks` key is not a JSON object (array, string, or `null`). Previously it silently overwrote the value with `{}` and rewrote the file, which could discard the user's hook config.
- **pidash**: bundled hooks (`set-attention`, `clear-attention`, `update-tasks`, `sync-agent-return`) now write `dev/local/autopilot/state.json` atomically via tempfile + `os.replace`. Previously a hook killed mid-write (SIGKILL, disk full) could leave a truncated `state.json`, which is the source of truth for every subsequent hook and the dashboard. The session-file writer (`~/.pidash/sessions/{id}.json`) was already atomic.
- **pidash**: bundled session hooks (`mirror_to_session_dir`, `cleanup-session`) now reject a `session_id` containing an embedded null byte instead of propagating `ValueError` from `tempfile.mkstemp`. The existing `except OSError` did not catch `ValueError`, so a malformed hook input could crash the hook with a stack trace; it now no-ops silently like other invalid-input paths.
- **pidash**: `pidash hooks install`/`uninstall` legacy-entry detection now matches by basename equality (`Path(token).name in LEGACY_HOOK_FILENAMES`) rather than substring. A user-written script whose filename happens to suffix one of the five legacy names (e.g. `backup-set-pidash-attention.py`) is no longer falsely flagged and removed.
- **bim**: `bim doc audit` walker now resolves each candidate path and skips entries (files or directories) whose target lies outside `<business_root>` after symlink resolution. Without this, a symlinked issuer subdir could make the audit traverse and report PDFs from anywhere on disk; the audit is documented as read-only against the Business folder and that boundary is now enforced.
- **bim**: `bim doc audit` now surfaces OCR/hash adapter failures as `ocr_check_failed` / `hash_check_failed` findings instead of silently treating the offending PDF as clean. Previously, an unreadable PDF, permission error, or buggy OCR adapter would produce no finding and bump the clean count, hiding the real failure mode. Read errors now flow into both stdout (✘ row) and JSON `pdf_findings` so the operator sees them.
- **bim**: `bim doc promote` now refreshes `state.db rule_matches` for triage proposals that originated from a rule-engine match. The pipeline records the winning rule_id on the `TriageProposal` (`applied_rule_id` field), and promote writes a fresh `last_matched_at` timestamp during the write path. Previously, only the auto-filing path refreshed rule freshness, so any rule whose matches consistently went to triage would falsely trigger the audit's 90-day staleness warning. Pre-existing proposals without `applied_rule_id` (default null) skip the refresh and behave as before.
- **bim**: `bim doc promote` now uses the triage proposal's `ingested-at` date for the `doc-date` fallback when a document has no extracted date (previously used `date.today()`, which made the same logical document yield different `doc-date` values when promoted on a different day from when it was triaged). Pipeline+promote consistency now holds for date-less documents too.
- **bim**: rule-engine conflict detection now flags two same-priority same-partial-ness rules pinning any shared field (was: only `issuer_slug`). Two rules pinning different `doc_type`, `doc_currency`, etc., are now correctly routed to triage with `rule_conflict: <id1> vs <id2>` instead of one silently winning.
- **bim**: `bim doc audit` walker now tolerates per-directory `OSError` (e.g. `PermissionError`) on `iterdir()` and continues with sibling directories, instead of aborting the entire audit on the first unreadable subtree. One misconfigured folder no longer blocks the rest of the report.
- **bim**: `bim doc audit` stdout no longer prints `0 low OCR confidence` when the OCR-quality reader cannot expose a confidence value for any walked PDF. The production pdfminer-based reader always returns `None` confidence, so the old line falsely implied the check ran successfully and found nothing. The reporter now emits `low OCR confidence: not assessed (reader does not expose confidence)` when no PDF was assessable, and the existing `{n} low OCR confidence` line whenever at least one PDF returned a real confidence value.
- **bim**: `bim doc audit` stdout no longer renders the `Watcher: not configured` stub row. The watcher heartbeat row appears only in spec §10's illustrative sample output, not in the normative §9 audit table that PRD 00037 imports, so emitting a stub line for it added noise. Sections now correspond 1:1 to §9; a watcher row will be reintroduced when the watcher heartbeat is wired up.

### Changed

- **pidash**: ``pidash`` is now a Click group. The TUI is still the default (``pidash`` with no args); to pass a project path explicitly, use ``pidash --project-path <path>`` or ``pidash tui <path>``. The previous positional ``pidash <path>`` form is no longer accepted.
- **bim**: `bim doc audit` JSON report adds a `non_clean_pdf_count` field so consumers have an exact partition with `clean_pdf_count` (`clean + non_clean == walked`). The audit's stdout is unchanged. Documentation now states explicitly that `pdf_findings` is one-entry-per-finding (a PDF with multiple findings appears multiple times sharing `pdf_path`), not one-entry-per-PDF, eliminating the previous doc/impl drift that PRD 00036 consumers might trip over.
- **bim**: `bim doc audit` "No conflicts" check now detects overlapping match clauses per spec §9, not only pinned-constant disagreement. Two enabled rules at the same priority are flagged whenever their `match` clauses are not statically provably disjoint (only `email_from_domain` literal-list disjointness is currently decidable; regex/substring clauses are conservatively treated as potentially overlapping). Disagreeing pinned `extract` values continue to be surfaced in the finding detail to help authors locate the conflict.
- **bim**: `Classifier.classify`/`classify_with_model`/`classify_with_pinned` now take a `SourceMetadata` dataclass instead of a `dict[str, object]` for `source_metadata`. The pipeline builds source metadata in one place (`Pipeline._build_source_metadata`) and feeds it to both the rule engine and the classifier, eliminating the previous parallel `_build_source_metadata` (dict) + `_build_rule_source_metadata` (dataclass) builders that could drift if a new metadata field was added to only one. Public CLI behaviour is unchanged.
- **bim**: triage proposals now carry the LLM-generated `summary` from extraction in their `zettel_preview.summary` field, and `bim doc promote` threads that summary into the promoted zettel body. Documents promoted from triage now match the ingest-path body shape (summary paragraph between the H1 and the `## OCR text` callout). Existing proposals without a `summary` field load unchanged (defaults to `None`).
- **bim**: `bim doc` zettels embed the source-file link in `file-path` frontmatter as `"[Open file](file://...)"` instead of an `[Open PDF]` link in the body (file-type-agnostic). The internal `DocumentZettelFrontmatter.file_path` attribute keeps a raw absolute path; the Markdown-link wrapping happens only at YAML serialisation time. Existing zettels are not rewritten.
- **bim**: zettel `ingested-at` frontmatter is now serialised with PyYAML's default space-separated form (`2026-05-04 14:30:22+02:00`) instead of T-separated. Round-trips via `datetime.fromisoformat` on Python 3.11+. v1 zettels written before this change (T-separated) still parse correctly; existing zettels are not rewritten.
- **bim**: default `classifier.primary_model` is now `qwen3:30b-a3b` (was `qwen2.5:7b-instruct`) and `classifier.fallback_model` is now `qwen3:14b` (was `qwen2.5:14b-instruct`). Users running with the default config will need `ollama pull qwen3:30b-a3b` (and `qwen3:14b` for the fallback) before `bim doc ingest` passes health check; users with an explicit `classifier.primary_model`/`fallback_model` override in their bim config are unaffected.

### Removed

- **build**: dropped Python 3.10 support. `requires-python` is now `>=3.11,<4.0`. The motivating constraint was the `ingested-at` `fromisoformat` round-trip in zettels, which on 3.10 required a custom YAML dumper to emit the T-separated form. With 3.11+ as the floor, the dumper is gone and the writer uses `yaml.safe_dump` directly. Users on 3.10 should upgrade to 3.11+ before installing 0.12+.

## [0.11.1] - 2026-05-10

### Added

- **bim**: doc rule engine v1 — deterministic per-issuer extraction before LLM fallback. New `bim doc rules` subcommand group (`list`, `validate`, `test`, `backtest`) for authoring and verifying rules. Existing `issuers.yml` files without `rules:` blocks load unchanged; full-rule matches set `extraction_method: rule:<id>:v<n>` and skip both Ollama calls, partial-rule matches set `extraction_method: rule+llm:<id>:v<n>` and reduce the prompt scope.
- **bim**: `bim doc ingest` shows a Rich spinner with per-stage labels (running OCR → classifying document → extracting fields) when stdout is a TTY; stays silent in batch/piped runs
- **bim**: `bim doc ingest` extractor now receives a `Hints:` block containing the original filename and email subject when known; the LLM uses these to ground field values when OCR text is noisy or numbers span line breaks (downloaded invoices often carry the invoice number as the filename)
- **bim**: `doc.ocr.extra_args` config field passes any extra `ocrmypdf` flags verbatim into both the redo and full-OCR branches (e.g. `--clean`, `--remove-background`, `--tesseract-pagesegmode 6`); the user owns flag correctness, the pipeline schema stays small

### Changed

- **bim**: doc zettel frontmatter and body switched to v1 shape: kebab-case keys (`doc-type`, `ingested-at`, `file-path`, ...), single `issuer` field (no more `issuer_slug`/`issuer_display`; the slug is in the canonical filename and `tags`), required `title` field, ISO 8601 datetime `ingested-at` with offset, source-file link in `file-path` frontmatter, optional LLM-generated summary paragraph, and per-issuer vault subfolder (`<vault>/<doc-subdir>/<issuer-slug>/<basename>.md`) mirroring the business-folder layout. `bim doc promote` preserves the triage proposal's `ingested-at`, so the same logical document driven through ingest vs promote now yields equivalent frontmatter (modulo `extraction-method`).
- **bim**: `bim doc ingest` extractor system prompt now spells out date/amount/currency formatting rules with examples (15.11.2024 → 2024-11-15, "1 234,56" → 1234.56, Kč → CZK), names the OCR-noise reconstruction expectation, and distinguishes invoice issue date from payment due date

### Removed

- **bim**: doc zettel body no longer renders `**Date:**` and `**Amount:**` metadata lines (information already lives in frontmatter)

### Fixed

- **bim**: `bim doc rules validate` now rejects `issuers: []` (and other falsy non-mapping shapes such as `issuers: ""` or `issuers: 0`) with a friendly `CommandResult` error, instead of silently collapsing them to "no issuers" via a `... or {}` short-circuit before the type guard ran
- **bim**: `doc ingest` now runs the LLM extractor whenever the classifier produced a `doc_type`, even when the issuer is unknown or classifier confidence is below `triage_threshold`. Triage proposals previously emitted nulls for `number`, `date`, `amount`, `currency`, and `title` because extraction was short-circuited; now the human reviewer sees the model's field-level output (full or partial) instead of a wall of nulls
- **bim**: `doc ingest` extractor now returns whatever fields it successfully coerced when raising `IncompleteExtraction` for missing/unparseable required fields; the pipeline surfaces this partial result in the triage proposal so coerced fields aren't discarded just because one required field is missing
- **bim**: `doc ingest` triage proposals now pre-fill the issuer slug with the classifier's slugified guess (when the LLM returned a slug not in the registry) so the human reviewer has a starting point instead of a blank field; `register_issuer` still defaults to `false` so registration requires explicit confirmation
- **bim**: expand `~` on every user-provided path in `doc.paths` (state_dir, vault_root, business_root, inbox_*, issuers_file, originals_dir) so `bim doc ingest` and `bim doc promote` no longer fail with `FileNotFoundError: '~/...'` when the config uses tilde paths
- **bim**: `doc ingest` and `doc promote` route missing-file errors through buvis console instead of Click's default `Usage: ... Error: ...` formatting
- **morph**: `html2md` and `deblank` route missing-path errors through buvis console
- **puc**: `strip` routes missing-file errors through buvis console
- **sysup**: `sysup nvim` no longer misreports successful mason installs as failures when `mason-tool-installer.nvim`'s `ensure_installed` mixes lspconfig names (`bashls`, `lua_ls`, `dockerls`, …) with mason package names. The probe now subscribes to `mason-registry`'s `package:install:failed` event before `MasonToolsUpdateSync` instead of querying `ensure_installed` entries by raw name, so the resolved mason package names are checked. Also strips iTerm2 OSC user-var escapes injected around the probe sentinels by shell integration

## [0.11.0] - 2026-05-06

### Added

- **bim**: doc subsystem v1 — ingest pipeline, triage workflow, issuer registry, OCR + LLM via Ollama/qwen2.5

### Changed

- **bim**: `bim doc ingest --strict` / `bim doc promote --strict` exits 1 on pipeline failure for scripting; default still exits 0
- **bim**: `bim doc ingest` and `bim doc promote` retry transient classifier/extractor failures up to `classifier.max_retries` times against `classifier.primary_model`, then fall back once to `classifier.fallback_model`. Semantic failures (JSON parse errors, missing/uncoercible fields from the classifier; field-derivation failures from the extractor) and timeouts now short-circuit to triage on the first attempt, no longer consuming the retry budget.
- **bim**: `DocPaths.business_root` must be under `Path.home()`; misconfigured paths now fail loudly at settings load instead of silently writing malformed `~<absolute>` strings into zettel frontmatter

## [0.10.0] - 2026-04-14

### Added

- **all tools**: `--update` flag force-checks PyPI and upgrades if a newer buvis-gems release is available; prints status or "already up to date"

## [0.9.0] - 2026-04-14

### Added

- **dot**: revert hunk or selected lines from diff pane with `r` (#78)

### Fixed

- **dot**: scroll diff pane to reveal content past the last hunk; add `ctrl+d`/`ctrl+u` half-page, `pagedown`/`pageup`, `g` (top), `G` (bottom) bindings (#77)
- **sysup**: capture mason probe output from stderr so per-tool OK/FAIL/INCONCLUSIVE states are reported again (#86)
- **sysup**: read mason ensure_installed from lazy.nvim plugin spec so per-tool install failures are detected (#87)

## [0.8.7] - 2026-04-14

### Changed

- **sysup**: `sysup nvim` mason step now fails when individual mason tools fail to install, reporting the missing tool names and a tail of `mason.log` instead of silently returning success

## [0.8.6] - 2026-04-12

### Added

- **dot**: persist diff pane scroll position when switching between files

### Fixed

- **dot**: scroll TUI panes to keep selected item visible during navigation
- **pidash**: scroll TUI panels and sidebar when content overflows viewport

## [0.8.5] - 2026-04-10

### Fixed

- **updater**: preserve installed extras when auto-updating in `pip` or `uv pip` venvs. Previously the upgrade command ran `pip install --upgrade buvis-gems` without extras, which silently removed previously installed extras (e.g. `dot`) on every upgrade and left tools like `dot` erroring with `dot TUI requires the 'dot' extra`

## [0.8.4] - 2026-04-10

### Fixed

- **sysup**: `sysup nvim` no longer hangs until the mason step timeout when `mason-tool-installer.nvim` is lazy-loaded. Force-loads mason plugins via `Lazy load` and uses the synchronous `MasonToolsUpdateSync` command so the subprocess exits as soon as the update completes

### Changed

- **sysup**: raise `sysup nvim` mason step timeout from 300s to 600s to accommodate slow package mirrors and cold proxy caches

## [0.8.3] - 2026-04-10

### Fixed

- **updater**: resolve the new binary path via `mise where pipx:buvis-gems` before re-exec, so upgrades on mise-managed installs no longer fail with `ENOENT`
- **updater**: exit cleanly instead of continuing after a successful upgrade when re-exec fails, avoiding cascading import errors from a partially-replaced venv

## [0.8.2] - 2026-04-10

### Changed

- **updater**: run auto-update check on every invocation (including `--version`, `--help`, and other eager callbacks) via a `click.Command.parse_args` patch scoped to `buvis_options` commands
- **updater**: silent operation — all update events now land in `~/.config/buvis/updater.json` (cache + rolling 100-entry log) instead of stderr, so tool output is never disturbed

## [0.8.1] - 2026-04-09

### Fixed

- **updater**: detect mise-managed pipx installations for auto-update
- **cli**: add missing CRITICAL log level to --log-level option

## [0.8.0] - 2026-04-09

### Added

- **gems**: auto-update check on CLI startup with installer detection and re-exec

## [0.7.0] - 2026-04-08

### Added

- **config**: `--feedback` flag on all CLI tools to open browser-based feedback form

### Fixed

- **dot**: only highlight selected file and update diff in the focused TUI pane
- **dot**: show GPG passphrase prompt before pull decryption in CLI mode

## [0.6.1] - 2026-04-08

### Fixed

- **sysup**: report nvim update progress per step instead of waiting until all steps finish
- **sysup**: include captured output in mason timeout error message

## [0.6.0] - 2026-04-07

### Added

- **sysup**: `nvim` command to update neovim plugins, mason tools, and treesitter parsers headlessly

## [0.5.2] - 2026-04-04

### Fixed

- **dot**: scroll file list panes to keep selected file visible when list overflows

## [0.5.1] - 2026-04-01

### Changed

- **pidash**: redesign state schema - rename description to issue, add cycle/consensus/action/reason/status/research fields, replace done_prds with BatchInfo, show resolution counts and batch progress

### Fixed

- **dot**: remove console import from commands layer (commands return CommandResult, CLI handles output)

## [0.5.0] - 2026-04-01

### Added

- **pidash**: multi-session mode - `pidash` (no args) watches `~/.pidash/sessions/` and shows all active sessions in sidebar + detail layout
- **pidash**: session sidebar with project name, phase badge, attention indicator, stale/done dimming
- **pidash**: keyboard navigation (up/down) to switch between sessions
- **pidash**: stale session detection (5min threshold, dimmed in sidebar)
- **pidash**: `--cleanup` flag to remove session files older than 24h
- **pidash**: auto-cleanup of stale session files on multi-session startup
- **pidash**: doubt-review phase in pipeline (CATCHUP → PLANNING → WORKING → REVIEWING → DOUBT → DONE)
- **pidash**: dedicated Doubts panel for doubt review findings
- **pidash**: render `[C{n}]` cycle tags in magenta, `[DOUBT]` tags in cyan
- **pidash**: render `[D{n}]` decision tags in task panel
- **dot**: `delete` command for removing files from tracking and disk (handles git-secret cleanup)
- **dot**: TUI mode - interactive terminal UI for dotfiles management (`dot` or `dot tui`)
- **dot**: TUI colored diff preview with auto-update on cursor movement
- **dot**: TUI commit modal, gitignore modal, delete confirmation dialog
- **dot**: TUI push/pull/refresh keybindings (p/P/r)
- **dot**: TUI space key as stage/unstage toggle
- **dot**: TUI hunk-level staging/unstaging (enter on focused hunk in diff pane)
- **dot**: TUI line-select mode for fine-grained staging (v to enter, space to toggle lines, enter to stage)
- **dot**: TUI file browser for discovering untracked files (b key, browse directories with tracking status)
- **dot**: TUI secrets panel for git-secret management (S key, reveal/hide/register/unregister)
- **dot**: TUI quick encrypt from any view (e key, register file with git-secret)
- **dot**: TUI configurable theme via `BUVIS_DOT_THEME` env var
- **dot**: TUI confirm-quit dialog on unsaved changes
- **dot**: TUI unpushed/unpulled arrow indicators in status bar

### Changed

- **dot**: `rm` command now keeps file on disk (uses `--cached`), use `delete` to remove from disk

### Fixed

- **pidash**: correct STATE_DIR from `.local/autopilot` to `dev/local/autopilot`
- **pidash**: escape brackets in task names to prevent Rich markup swallowing
- **dot**: GPG passphrase prompt in TUI instead of blocking on pinentry
- **dot**: auto-configure fetch refspec for bare repo remote tracking
- **dot**: fall back to `origin/<branch>` when `@{u}` upstream not set
- **dot**: refresh widgets immediately after list updates
- **dev**: `release local` reliably restores pyproject.toml after build
- **dev**: extract changelog from CHANGELOG.md for release notes
- **ci**: bump requests for CVE-2026-25645, ignore unfixable pygments CVE

## [0.4.0] - 2026-03-22

### Added

- **pidash**: new Textual TUI dashboard for monitoring autopilot PRD cycle status
- **pidash**: attention overlay when Claude needs permission approval
- **pidash**: animated braille spinner for active phases, task list with status markers
- **dot**: report unpushed/unpulled commits in status
- **dot**: skip push when nothing to push, hint GPG on pull failure
- **dev**: `release local` for .devN test builds
- **dev**: automate pyproject.toml tool wiring for new tools
- **ci**: split test matrix into lib + per-tool jobs

### Changed

- **zettel**: flatten fixers/upgrades directory structure
- **config**: consolidate paths, source, generators into fewer modules
- **pybase**: move DirTree from shared library to muc (sole consumer)
- **fctracker**, **pinger**: return CommandResult on error instead of raising exceptions
- **console**: exit with code 1 in panic()
- **deps**: replace bincode with rmp-serde, bump cache version to 4
- **deps**: upgrade textual 3.7→8.1, vite 8, marked 17

### Fixed

- **fren**: decode RFC 2047 encoded EML headers before slugifying
- **fren**: slug lowercase and eml timestamp format
- **bim**: run svelte-kit sync before vite build
- **dot**: replace pexpect with subprocess.run in shell interact
- **dot**: stage .gitignore in encrypt to prevent plaintext staging
- **dot**: push when upstream unknown, add supports dirs
- **dot**: add untracked files when adding a directory
- **pybase**: return actual stderr on failure, discard stderr on success

## [0.3.2] - 2026-02-24

### Added

- **dot**: staged/unstaged status, unstage command, commit positional arg

## [0.3.1] - 2026-02-24

### Added

- **dot**: encrypt and run commands

### Fixed

- **dot**: show deleted/new/renamed files in status, add missing pull steps

## [0.3.0] - 2026-02-24

### Added

- **fren**: file renamer toolkit — slug, directorize, flatten, normalize commands
- **morph**: file conversion toolkit — html2md and deblank commands
- **netscan**: network scanner tool
- **puc**: photo utility collection tool
- **sysup**: system update tool
- **vuc**: video utility collection tool
- **muc**: cover command for duplicate cover cleanup
- **dot**: pull, commit, push commands
- **ci**: SLSA build provenance attestation and SBOM generation

### Changed

- **console**: extract report_result, require_import, validate_path helpers

### Fixed

- **fren**: narrow broad except in EML slug fallback
- **morph**: avoid unlinking before restore in deblank
- **ci**: downgrade upload/download-artifact to v4

## [0.2.3] - 2026-02-20

### Fixed

- **jira**: populate environment field on issue creation

## [0.2.2] - 2026-02-20

### Fixed

- **bim**: sync description from zettel to linked jira issue
- **rust**: preserve reference section order using IndexMap

## [0.2.1] - 2026-02-20

### Fixed

- **config**: skip world-writable check on Windows

## [0.2.0] - 2026-02-20

Initial release.

### Added

- **pybase**: shared library — adapters, configuration, filesystem, formatting utilities
- **zettel**: subsystem with domain logic, Jira integration, and Rust extension (PyO3) for YAML scanning
- **bim**: BUVIS InfoMesh CLI — query engine with expression language, multiple output formats (table, json, jsonl, html, pdf, tui, kanban), web dashboard (SvelteKit), create/edit/show/delete/archive/format/import/sync commands
- **dot**: dotfiles manager with status and add commands
- **fctracker**: foreign currency account tracker
- **hello_world**: sample script template
- **muc**: music collection tools
- **outlookctl**: Outlook CLI
- **pinger**: ICMP ping utilities
- **readerctl**: Readwise Reader CLI
- **zseq**: Zettelsequence utilities
- **zettel**: metadata cache for fast filtered queries, recurrence parsing, expand directive, subclass instantiation
- **config**: Pydantic-based settings with Click option generation
- **ci**: GitHub Actions with test matrix, coverage, ruff lint, mypy, dep audit, GitHub releases

[Unreleased]: https://github.com/buvis/gems/compare/gems-v0.13.0...HEAD
[0.13.0]: https://github.com/buvis/gems/compare/gems-v0.12.6...gems-v0.13.0
[0.12.6]: https://github.com/buvis/gems/compare/gems-v0.12.5...gems-v0.12.6
[0.12.5]: https://github.com/buvis/gems/compare/gems-v0.12.4...gems-v0.12.5
[0.12.4]: https://github.com/buvis/gems/compare/gems-v0.12.3...gems-v0.12.4
[0.12.3]: https://github.com/buvis/gems/compare/gems-v0.12.2...gems-v0.12.3
[0.12.2]: https://github.com/buvis/gems/compare/gems-v0.12.1...gems-v0.12.2
[0.12.1]: https://github.com/buvis/gems/compare/gems-v0.12.0...gems-v0.12.1
[0.12.0]: https://github.com/buvis/gems/compare/gems-v0.11.1...gems-v0.12.0
[0.11.1]: https://github.com/buvis/gems/compare/gems-v0.11.0...gems-v0.11.1
[0.11.0]: https://github.com/buvis/gems/compare/gems-v0.10.0...gems-v0.11.0
[0.10.0]: https://github.com/buvis/gems/compare/gems-v0.9.0...gems-v0.10.0
[0.9.0]: https://github.com/buvis/gems/compare/gems-v0.8.7...gems-v0.9.0
[0.8.7]: https://github.com/buvis/gems/compare/gems-v0.8.6...gems-v0.8.7
[0.8.6]: https://github.com/buvis/gems/compare/gems-v0.8.5...gems-v0.8.6
[0.8.5]: https://github.com/buvis/gems/compare/gems-v0.8.4...gems-v0.8.5
[0.8.4]: https://github.com/buvis/gems/compare/gems-v0.8.3...gems-v0.8.4
[0.8.3]: https://github.com/buvis/gems/compare/gems-v0.8.2...gems-v0.8.3
[0.8.2]: https://github.com/buvis/gems/compare/gems-v0.8.1...gems-v0.8.2
[0.8.1]: https://github.com/buvis/gems/compare/gems-v0.8.0...gems-v0.8.1
[0.8.0]: https://github.com/buvis/gems/compare/gems-v0.7.0...gems-v0.8.0
[0.7.0]: https://github.com/buvis/gems/compare/gems-v0.6.1...gems-v0.7.0
[0.6.1]: https://github.com/buvis/gems/compare/gems-v0.6.0...gems-v0.6.1
[0.6.0]: https://github.com/buvis/gems/compare/gems-v0.5.2...gems-v0.6.0
[0.5.2]: https://github.com/buvis/gems/compare/gems-v0.5.1...gems-v0.5.2
[0.5.1]: https://github.com/buvis/gems/compare/gems-v0.5.0...gems-v0.5.1
[0.5.0]: https://github.com/buvis/gems/compare/gems-v0.4.0...gems-v0.5.0
[0.4.0]: https://github.com/buvis/gems/compare/gems-v0.3.2...gems-v0.4.0
[0.3.2]: https://github.com/buvis/gems/compare/gems-v0.3.1...gems-v0.3.2
[0.3.1]: https://github.com/buvis/gems/compare/gems-v0.3.0...gems-v0.3.1
[0.3.0]: https://github.com/buvis/gems/compare/gems-v0.2.3...gems-v0.3.0
[0.2.3]: https://github.com/buvis/gems/compare/gems-v0.2.2...gems-v0.2.3
[0.2.2]: https://github.com/buvis/gems/compare/gems-v0.2.1...gems-v0.2.2
[0.2.1]: https://github.com/buvis/gems/compare/gems-v0.2.0...gems-v0.2.1
[0.2.0]: https://github.com/buvis/gems/releases/tag/gems-v0.2.0
