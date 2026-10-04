# buvis-gems Evolution Assessment — 2026-07-09

Full-battery self-assessment (7 parallel read-only lenses, load-bearing claims verified against source). Companion to `evolution-roadmap.md` (the ordering authority) and PRDs `00041`–`00061` in `dev/local/prds/backlog/`.

## Verdict in three sentences

The architecture is **fundamentally sound and the stated future goal is already reachable**: the zettel clean-architecture layering holds with zero violations, tool isolation is total, the `CommandResult` discipline is honored everywhere it should be, and the all-interface goal already has a **working exemplar** (bim's CLI + TUI + serve-API all drive the same command classes through the `bim/dependencies.py` composition root). The faults are **localized, not systemic**: one Critical security hole (`bim serve` is unauthenticated and unconfined), a cluster of quiet data-loss bugs in the note/PDF write paths, and a duplication tax where a few interfaces (dot's TUI, parts of bim's serve/TUI) reimplement logic instead of consuming the proven seam — which is exactly where the commit history shows 6× the fix density. The route back on track is: **stop the bleeding (P0), converge the correctness gaps (P1), then finish the one half-built seam that makes every future interface cheap (P2)**.

## What the architecture gets right (do NOT "fix" these)

- **Zettel clean architecture is real.** 0 layer violations across domain → application → infrastructure → integrations (full import sweep). `adapters` is imported only from `integrations/` (Jira DTO), which is that layer's job.
- **Hard tool isolation.** 0 cross-tool imports, 0 lib→tools imports across all 16 tools.
- **`CommandResult` discipline holds.** 0 `sys.exit` / `console.panic` / `raise SystemExit` inside any `src/tools/*/commands/**`; single definition at `result.py:31`.
- **The all-interface rule already works in bim.** CLI (`cli.py`), TUI (`tui/query.py`), and API (`serve/_actions.py`) all drive the same `Command*` classes via `bim/dependencies.py`. dot is the outlier.
- **Money math is safe.** fctracker is `Decimal` end-to-end from CSV strings; rounding only at presentation; it never writes the ledger.
- **The bim doc filing order is loss-free** (zettel → PDF move → DB row; crash leaves exactly one PDF path, nothing deleted before the archive copy exists; cross-volume `os.replace` fails loud). **OCR preserves originals** (pre-OCR bytes backed up via atomic write). **sqlite state_db** is WAL + transactional + race-safe claim.
- **The Rust/Python dual parser is not dead code** — the Python fallback is the tested parity oracle (`tests/lib/zettel/parity/`) and the no-wheel escape hatch. Keep both.

## Findings (ranked; NEW unless marked)

Severity: **C**ritical / **H**igh / **M**edium / **L**ow. Lens key: ARCH, OPS (operational safety), SEC, IFACE (interface cost-of-change), SIMP (simplification), HIST (commit history), USER (user-facing).

### P0 — data-loss and critical security

| # | Sev | Lens | Defect | Evidence (verified) | PRD |
|---|-----|------|--------|---------------------|-----|
| 1 | H | OPS/ARCH/SIMP | Every note save is truncate-then-write; a crash or ENOSPC mid-write destroys the note with no backup. Single write path for edit/create/sync/archive/format/WebUI-PATCH. | `markdown_zettel_repository.py:55` bare `Path(...).write_text(...)`; correct pattern already exists at `doc/shared/atomic_write.py:16-34` | 00041 |
| 2 | C | SEC | `bim serve` exposes unauthenticated arbitrary file **read / overwrite / delete** — path params are never confined to the vault, and the app has no auth / no `TrustedHostMiddleware`. | `_routes.py:160-174` (GET), `:136-157` (PATCH `write_text`), `_actions.py:135-144` (delete) all `Path(file_path)` with only `is_file()`; `_app.py:14-41` no middleware; `-H 0.0.0.0` available | 00042 |
| 3 | H | OPS | `bim doc promote` overwrites an existing archive PDF + zettel on canonical-name collision (promote timestamps are always `…000000`, so time never disambiguates). Ingest has collision handling; promote skips it. | `promote.py:218` builds target with no exists-check, `:256` `source_pdf.replace(target)`; ingest resolver at `pipeline.py:722-758` | 00043 |
| 4 | H | OPS | Ctrl-C (or any `BaseException`) mid-ingest permanently parks the document as "duplicate": the claim is released only on `except Exception`, so `KeyboardInterrupt` escapes; no `finally`, no TTL, no clear command. | `pipeline.py:178-197` (`except Exception` releases; `KeyboardInterrupt` is `BaseException`) | 00044 |
| 5 | M-H | OPS/SEC | Encrypted `dot rm` destroys **both** plaintext and ciphertext (rm == delete for secrets); and the filename is f-string-interpolated into a `shell=True` command (injection / whitespace breakage). | `dot/commands/rm/rm.py:46` `secret remove -c`, `:60-65` unlinks plaintext; `:38,46` unquoted `{self.file_path}` into `ShellAdapter.exe` | 00045 |

### P1 — correctness / convergence

| # | Sev | Lens | Defect | Evidence (verified) | PRD |
|---|-----|------|--------|---------------------|-----|
| 6 | H(user) | USER | dot TUI unstaged pane silently hides changed git-secret files until CLI `dot status` runs first — risks never committing a secret change (issue #92, open, 3 months). | CLI hides before status (`status.py:39-45`); TUI `GitOps.status()` never does (`git_ops.py:42-44`), only at commit (`:88-92`) | 00046 |
| 7 | M | OPS | Auto-updater re-exec failure logs to a JSON file only, then `sys.exit(0)` — a scripted `bim …` exits 0 having done nothing, printed nothing. | `updater/executor.py:140-147`; runs before every command via `click_integration.py:160-173` | 00047 |
| 8 | M | OPS | fctracker computes FIFO cost basis from raw CSV order (`rows.insert(0,row)` assumes newest-first) with **zero validation** → wrong money on a natural chronological ledger; overdraft/bad-row raise raw tracebacks. | `transactions_reader.py:27-28,31`; `quantified_queue.py:32`, `account.py:42`; commands catch only `FileNotFoundError` | 00048 |
| 9 | M | OPS/tracked | pidash `state.json` lost-update race between concurrent hook processes (unlocked read-modify-write); atomic write prevents torn files but not interleaving. Plus tracked #111 (fsync), #112 (order), #113/#114. | `hooks/update_tasks.py:182-193`, `sync_agent_return.py:124-141`; no `flock` anywhere | 00049 |
| 10 | M | ARCH | Rust/Python scanner parse errors are silently discarded; a poisoned note vanishes from query/TUI/API results with no signal, and the two backends disagree on failure semantics. | `markdown_zettel_repository.py:92,94` (`_errors` dropped); Python fallback (97-110) collects none | 00050 |

### P2 — leverage (the one root cause behind many findings)

The all-interface goal has a **proven seam but it is not mandatory**, so logic drifts across interfaces. This is the single highest-leverage phase.

| # | Sev | Lens | Defect | Evidence (verified) | PRD |
|---|-----|------|--------|---------------------|-----|
| 11 | M | IFACE | The rule has no artifact: one AGENTS.md bullet, no design doc, no scaffold support, no parity check. Coverage: API/WebUI 1/16, TUI 3/16. | `AGENTS.md:67`; repo-wide rg | 00051 |
| 12 | M | ARCH | Importing `pybase.configuration` monkey-patches Click globally at **import time** and makes Click a hard dep of every consumer — a FastAPI/WebUI/TUI process cannot load settings without it. `sys.exit`/`click.echo` in uv & updater layers compound this. | `click_integration.py:179` module-level `_install_parse_args_patch()`; `adapters/uv/*` (7 `sys.exit`), `updater/*` (14 `click.echo`) | 00052 |
| 13 | H | ARCH/IFACE/HIST | dot TUI reimplements the entire git command set (15 public `GitOps` methods; commit/pull incl. submodule + git-secret policy duplicated), a third mini-layer under `tui/commands/`. This is where the dot bug cluster lives; dot carries 14.2 fixes/kloc. | `git_ops.py:76-133` vs `commands/{commit,pull,…}`; HIST: dot 46 fixes/158 commits | 00053 |
| 14 | H | IFACE | Interface drift already shipped: PATCH route writes inline (bypasses `UpdateZettelUseCase`); WebUI shows failed actions as success (handlers return HTTP 200 `{"status":"error"}`); TUI create bypasses `CommandCreateNote` (skips validation/defaults); several screens discard `CommandResult`. `CommandResult.to_dict()` ("for API responses") has zero callers. | `_routes.py:136-157`; `_actions.py:62-89`; `tui/create_note.py:163-181`; `tui/edit_note.py:190-198`; `result.py:41-50` | 00054 |
| 15 | M-H | ARCH/HIST | `bim/cli.py` is a 773-line god registry (55 commits, feat 23 / refactor 21 / fix 8); every bim feature grows this one file past the 800 cap while hand-rolling result rendering that `console.report_result` exists for (used 0×, hand-rolled 52×). | `bim/cli.py`; twin `test_cli.py` 613 LOC | 00055 |

### P3 — enablement and top user wins

| # | Sev | Lens | Defect / opportunity | Evidence | PRD |
|---|-----|------|----------------------|----------|-----|
| 16 | M(user) | OPS/USER | The promised `bim doc migrate-layout` is unshipped — `legacy_layout_zettels` inflates every audit's `non_clean` forever; users hand-move files and break the frontmatter link. | README:121-123, `audit/*`; no migration command (rg) | 00056 |
| 17 | M(user) | USER | Reviewing a triaged PDF means hand-locating YAML under `_triage/`, editing `approved: true`, then `bim doc promote <path>` per file — the clunkiest step of the most-used workflow. No doc verbs in the WebUI action registry. | `bim.rst:349-364`; `serve/_actions.py:175-184` (note verbs only) | 00057 |
| 18 | H | HIST | dot diff/scroll viewport math lives as index arithmetic inside the Textual widget; every edge (headerless diff, single hunk, past-last-hunk) shipped as a fresh prod bug (6 scroll fixes in 3 days). | `diff_view.py` 18 commits/9 fixes; chain `4abf1c3`…`9d06d0a` | 00058 |
| 19 | H | HIST | pidash TUI churns because layout is verified by eyeballing a live TUI and `state.py` is an implicit mirror of the external autopilot skill's JSON that drifts under it (19-fix chain; 15.1 fixes/kloc). | `pidash/tui/app.py` 26 commits/19 fixes; `state.py` re-fixed `19286fb`,`77d451e`,`8a2ee80` | 00059 |

### Hygiene — deletion / librarization

| # | Sev | Lens | Opportunity | Evidence | PRD |
|---|-----|------|-------------|----------|-----|
| 20 | leverage | SIMP | Delete `adapters/uv` (620 LOC incl. tests, **zero production consumers**, superseded by updater), `hello_world` tool (440 LOC, not referenced by scaffold.py), `configuration/examples/` (182 LOC, test-only). ~1,240 LOC. | rg: uv adapter used only by its own `__init__`; scaffold generates from inline templates | 00060 |
| 21 | leverage | SIMP | Prune dead formatting surface (~400 LOC: `slugify`/`prepend`/`word_level_tools`/`humanize`/`as_graphql`, kept alive only by tests) down to the 4 live methods; relocate the Ollama HTTP client `suggest_tags` out of the formatting package into bim (wrong-layer). | 4 production callers total across the 642-LOC package | 00061 |

**Four divergent atomic-write implementations** (`doc/shared/atomic_write.py` with fsync, `pidash/hooks/session.py` without, `pidash/commands/hooks/settings.py` a third copy, `updater/state.py` **not atomic at all**) converge onto PRD 00041 (lift to `pybase/filesystem/`) + 00049 (pidash repoint).

## Checked and ruled safe (with evidence — do not spend effort here)

- **Updater command construction** — no injection from PyPI JSON: version validated via `packaging.version.Version()`, upgrade commands are hardcoded tuples, `subprocess.run(list-form)`, re-exec `os.execvp(list-form)`.
- **YAML** — `safe_load` / custom `_ZettelSafeLoader` everywhere; no `yaml.load(Full/Unsafe)` in `src/`.
- **Rust parser** — one poisoned note cannot brick a scan: malformed YAML → `(None, …)`, per-file errors pushed to a returned vec, `sections[0]` guarded; remaining `unwrap` are on `LazyLock` regex constants / post-match groups / test code.
- **PDF-ingest path construction** — traversal blocked at two layers (`SLUG_REGEX` on issuer, `DOC_TYPES` whitelist, `Path(...).name` basename, absolute-path validator on frontmatter).
- **netscan / muc / vuc / morph** — all subprocess calls list-form; hostnames via `ipaddress`, ports `str(int)`, media filenames as argv (ffmpeg-python / list args), timeouts set.
- **Secrets not logged** — Jira token is `SecretStr`; Readwise token not printed. (Gap: readerctl/readwise token file is written world-readable — minor, folded into 00047's neighbourhood if touched.)
- **fren / morph deblank / muc / bim import / archive_note / config_writer / zseq / dot TUI patch** — collision-resolved, backup-before-mutate, copy-then-delete, or read-only. Verified individually.

## Downstream note

There is no separate downstream repo: "downstream" is Bob's daily use plus the PyPI package, and internally the 16 tools consuming `pybase` (lib-zettel has exactly one consumer today — bim — which is why its query API co-changes 1:1 with bim). The deletion ledger below is the "paying down the tax" signal. The one real downstream-shaped tax is the **interface duplication** (P2): each interface that reimplements logic is a consumer that wrote glue it should have inherited.

### Deletion ledger (PRD → LOC removed)

| PRD | Removes | Net LOC |
|-----|---------|--------:|
| 00060 | uv adapter + hello_world + configuration/examples (all test-backed dead weight) | ~1,240 |
| 00061 | dead formatting surface + suggest_tags relocation | ~470 |
| 00041 | 3 of 4 atomic-write copies collapse to one shared helper | ~40 + a silent bug fix |
| 00053 | dot `GitOps` ↔ `commands/*` duplication collapses to one service | ~150 |
| 00055 | `bim/cli.py` result-rendering boilerplate → `report_result` | ~80 |

## Top 3 user-facing wins (compete with the safety fixes for the same hands)

1. **Fix #92** (dot TUI secret-status) — small, root cause located, near-zero risk; the daily dotfiles loop stops silently hiding secret changes. → 00046.
2. **Ship `bim doc migrate-layout`** — lets the flagship `bim doc audit` reach a clean baseline instead of permanently red. → 00056.
3. **`bim doc triage` review surface** — removes the clunkiest step of the most-invested workflow. → 00057. (Risk: verify the triage queue is actually non-trivial before building.)

Honorable mentions: batch-close pidash #111–114 (each carries a fix sketch) → folded into 00049; declare the tail tools (netscan/vuc/puc/morph/zseq/outlookctl/fren/pinger) maintenance-only so effort concentrates on bim/dot/pidash/sysup where all demonstrated demand lives → recorded in AGENTS.md.

## Method / honesty notes

- Seven lenses ran as isolated read-only auditors; the orchestrator re-read every load-bearing cited line before it drove a P0/P1 decision (serve routes, note-save, promote, claim-leak, dot rm, updater state, click patch, action registry — all confirmed).
- The task premise "many issues open" was **wrong**: only #92 and pidash #111–114 are open; #77/#78/#86/#87 are already fixed. Corrected here.
- Commit history is ~110 days (first real code 2026-02-12), not 18 months — so "churn over 18 months" = full history. Fix share is 21% of commits, concentrated in the two ad-hoc Textual TUIs, calmest in the DDD-structured zettel core (0.13 ratio). This is the empirical case for the P2 seam.
