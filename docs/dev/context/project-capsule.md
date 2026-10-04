# Project Capsule: buvis-gems

Generated: 2026-05-11; evolution assessment 2026-07-09; refreshed 2026-08-16 (autopilot batch 202608151500, full catchup re-run — HEAD advanced to `1390b82d`: PRD 00052 converged in cycle 1 and closed done, plus a docs commit flipping AGENTS.md's interface-agnostic-library invariant from GAP to HOLDS now that 00052 landed. PRD 00053 (dot git-ops unification) selected next and moved `backlog/` → `wip/`. GitHub state re-checked: no material change (same 1 open issue #92, same 5 open dependency PRs, master CI still green, last green run 2026-08-15). Re-refreshed same day (full catchup, HEAD advanced `1390b82d` → `ea423d34`): 00053 tasks 5 and 6 landed (CLI commit/push/pull, then CLI rm/delete/encrypt, both rewired to `DotGitService`) — 6/12 tasks done, no material GitHub-state change. Refreshed 2026-08-17 (full catchup, HEAD advanced `4bfb4a59` → `ca3e56cb`): 00053 stalled on task 12's false premise and was parked to `hold/`; 00054 (bim-serve-tui-convergence) selected next, task 1/5 done (server envelope + status mapping, 2 review-fix cycles), resuming at task 2. GitHub state re-checked: no material change (same 1 open issue #92, same 5 open dependency PRs, master CI still green, last green run 2026-08-16). Engram related-context and review-harvest results unchanged from the prior pass. Refreshed 2026-08-17 (full catchup, HEAD advanced `ca3e56cb` → `7a173cd3`): 00054 (bim-serve-tui-convergence) converged in 2 cycles and closed done — full PATCH/action/TUI convergence through command classes, `notify_result` failure surfacing wired through EditScreen/EditNoteApp/query TUI, error responses fail closed with envelope-shaped bodies. 00055 (bim-cli-modularization) selected next, moved `backlog/` → `wip/`, no tasks planned yet. GitHub state re-checked: no material change (same 1 open issue #92, same 5 open dependency PRs — #131/#120/#116/#115/#103 all still open and stale/frozen per prior notes — master CI green, last run 2026-08-17). Refreshed 2026-08-17 (full catchup, HEAD advanced `7a173cd3` → `95eb46c5`): 00055 tasks planned (9 tasks), task 1 (extract `doc_cli.py` as self-registering module) landed clean (reviewed NO FINDINGS), resuming build at task 2 (`serve_cli.py`) after a task-boundary session handoff. GitHub state re-checked: no material change (same 1 open issue #92, same 5 open dependency PRs, master CI still green, last run 2026-08-17). **Refreshed 2026-08-17 later (catchup + PR-merge planning, HEAD advanced `95eb46c5` → `816ee504`): 00055 tasks 2-4 landed plus 4 `report_result` swap commits and a merge commit. MASTER CI IS NOW RED — the prior "green" line above is superseded. Root cause confirmed from run 32008200774: `tests/tools/dot/test_tui_snapshots.py:57` sets `ops.status.return_value = staged + unstaged` (a flat 33-element list) while `DotGitService.status()` (`src/tools/dot/git/service.py:50`) returns `tuple[list[FileEntry], str | None]` — the app unpacks 2 from 33, `ValueError: too many values to unpack (expected 2)`, and all 10 dot snapshot tests fail (`10 failed, 645 passed, 5 skipped` in the `tools (ubuntu-latest, 3.12, dot)` job). This is exactly the unresolved cap_critical finding from parked PRD 00046, and it is now 00053's regression: the snapshot mock was never migrated when `GitOps` → `DotGitService` landed. `src/tools/dot/tui/git_ops.py` and `tests/tools/dot/test_git_ops.py` both still exist (00053 task 12 never ran). PR merge plan written to `dev/local/plans/pr-merge-plan-2026-08-17.md`.**

## Evolution roadmap (2026-07-09)

Full-battery self-assessment ran (7 lenses, verified). Verdict: architecture is sound and the all-interface goal is reachable — faults are localized, not systemic. Deliverables: `dev/local/audit-results/evolution-assessment-2026-07-09.md` (findings), `dev/local/audit-results/evolution-roadmap.md` (ordering authority), PRDs `00041`–`00061` in `backlog/`. Root cause behind the churn: the all-interface seam exists (bim `ACTION_HANDLERS` + command classes + `dependencies.py`) but isn't mandatory, so dot's TUI and parts of bim reimplement logic — the P2 phase (00051–00055) finishes it. P0 (00041–00045) is data-loss + a Critical `bim serve` security hole (unauthenticated arbitrary file read/write/delete); do it first. Guardrails added to AGENTS.md.

## Key Invariants

1. **Namespace package**: `src/lib/buvis/` must never have `__init__.py`
2. **All-interface rule**: every command must work across CLI, TUI, API, WebUI
3. **CommandResult pattern**: commands return `CommandResult`, CLI layer handles output/exit
4. **No console.panic() in command classes**: only in CLI layer
5. **Lazy imports in CLI handlers**: import command classes inside handler functions
6. **No Python logging**: use `buvis.pybase.adapters.console` everywhere
7. **Modern type hints**: `from __future__ import annotations`, `X | None` not `Optional[X]`
8. **Python 3.11+** (3.10 dropped in commit 6b767a5; `tomllib`, `datetime.UTC` available)
9. **Rust .so needs manual rebuild + codesign** during dev (macOS `syspolicyd` blocks unsigned)
10. **Explicit version in pyproject.toml** (maturin needs it at build time)
11. **Each tool has manifest.toml** - used by scaffold.py and check_tool_wiring
12. **TUI staging uses s/u keys** (not space as PRD originally stated) - implemented in foundation PRD
13. **GitOps returns CommandResult** for mutations, raw strings for queries (diff, status)
14. **DiffView is a simple Widget** with `render() -> Text` - currently read-only, returns styled Rich Text
15. **pidash STATE_DIR**: corrected to `dev/local/autopilot` (was `.local/autopilot`)
16. **BUVIS_SKIP_FRONTEND=1** skips `npm ci` + `npm run build` in `hatch_build.py::_build_frontend`. Set at workflow level in test.yml, update-snapshots.yml, and deploy-docs.yml. `publish.yml::build-wheels` intentionally omits it so release wheels ship with the built frontend. bim's `create_app` already falls back gracefully when `static/` is missing.

## Architecture Decisions

- Single PyPI package (`buvis-gems`) ships all 16 CLIs; extras control optional deps
- Rust extension via PyO3 for perf-critical zettel YAML scanning; Python fallback not maintained
- hatchling + custom build hook invokes maturin for Rust compilation
- Tools use Click for CLI, pydantic-settings for config, Rich for console output
- bim has a SvelteKit WebUI frontend under `bim/commands/serve/frontend/`
- dot TUI uses Textual framework with Screen-based architecture (DotApp -> MainScreen)
- pidash TUI uses Textual with flat widget layout (no screens), file watcher in thread worker
- Session hooks (PRD 00015) mirror autopilot state to `~/.pidash/sessions/{session_id}.json` atomically
- Session file format: full autopilot state + `session_id`, `cwd`, `updated_at` fields
- pidash multi-session mode: `pidash` (no args) watches `~/.pidash/sessions/`, sidebar + detail layout

## Component Boundaries

- `src/lib/buvis/pybase/` - shared library, no tool-specific logic
- Each `src/tools/<name>/` is self-contained; cross-tool imports prohibited
- Zettel subsystem has clean architecture layers: domain -> application -> infrastructure -> integrations
- Console adapter is the only output channel - no direct print/logging
- pidash: `tui/state.py` parses state JSON via Pydantic, `tui/watcher.py` watches files, `tui/widgets.py` renders, `tui/app.py` composes widgets and handles messages
- Session hooks live in `~/.claude/hooks/` (outside repo), shared helper at `pidash_session.py`

## Active Work

### Batch 202608151500 (launched 2026-08-15)
- [x] 00041-atomic-write-foundation-v1.md (2 cycles + blind + doubt → done). Lifted `bim/commands/doc/shared/atomic_write.py` into `pybase/filesystem/atomic_write.py`, repointed `MarkdownZettelRepository.save`, `updater/state.py::_write_state`, 6 bim doc callers, `sync_note.py`, `format_note.py`, `serve/_routes.py`, and 2 remaining bare note writes; deleted the doc-local module. First PRD of the 2026-07-09 evolution roadmap (`00041`-`00061`) — see [[evolution-roadmap-2026-07]].
- [ ] 00042-bim-serve-confinement-and-auth-v1.md — **PARKED to `dev/local/prds/hold/`** (cap_critical stall, 2026-08-15). Build gate landed all 5 tasks clean (3782 passed + mypy clean) and handed off to review. Cycle 1 rework fixed an unauthenticated-RCE and a token-disclosure-via-non-loopback-bind finding inline. Cycle 2 hit `rework_cap` 2 with one unresolved CRITICAL still open: task 6 gated `POST /api/queries/{name}/exec` and `/_adhoc` with `require_token` but never updated the frontend, so `execQuery`/`execAdhoc` in `api.ts` send no `X-Buvis-Token` and every WebUI dashboard query 401s (breaks the PRD's own Success Metric 3); also `exec_adhoc` discards `confine_path`'s resolved paths and re-resolves the client strings. Both fixes are small (see `dev/local/reviews/00042-bim-serve-confinement-and-auth-v1-review-02.md` Outcome section). Two CRITICAL findings were raised and DISCARDED as out-of-diff (pre-existing `python_eval` full-builtins RCE on `_adhoc`; unsanitized `{@html marked.parse(...)}` XSS in `MarkdownEditor.svelte`) — both real product risk, both unowned, both worth a follow-up PRD. **To resume: `mv dev/local/prds/hold/00042-bim-serve-confinement-and-auth-v1.md dev/local/prds/backlog/`** — autopilot never reads `hold/` on its own.
- [x] 00043-bim-doc-promote-collision-v1.md (2 cycles + blind + doubt → done). `bim doc promote` no longer overwrites an existing archived PDF+zettel on canonical-filename collision — reuses the seconds-increment collision resolver ingest already had, extracted into `shared/naming.py::resolve_collision` and shared by both call sites. Cycle 2 tail-sweep closed six test-quality/message-accuracy findings.
- [x] 00044-bim-doc-claim-dedup-integrity-v1.md (2 cycles + blind + doubt → done). Stale-claim predicate + opt-in max-age reclaim on StateDB, `claim_max_age_minutes` setting; claim release on any exit via try/finally; raw source sha recorded on triage and promote so dedup identity survives triage→promote. Cycle 2 tail-swept 10 medium/low findings (extracted `_delete_stale_claim`, guarded a BLOB-valued `claimed_at` TypeError, shared the pending-triage sentinel, test-module hygiene).
- [x] 00045-dot-rm-safety-v1.md (2 cycles → done, converged with deferrals at `rework_cap`). Encrypted `dot rm` now untracks (not deletes) both plaintext and ciphertext, quotes filenames against the `shell=True` injection hole; cycle 1 rework fixed a plaintext un-ignore regression and an incomplete ciphertext untrack. Cycle 2 hit `rework_cap` 2 with 15 unresolved findings (2 high, 9 medium, 4 low) recorded as cap-overflow deferrals in `dev/local/autopilot/deferred/202608151500-deferred.json`. Load-bearing one: `cfg rm --cached <file>.secret` exits 128 when the ciphertext is not in the index (a regression from this PRD's own cycle-1 rework) — fix is one flag (`--ignore-unmatch`); raise first at batch-end review.
- [ ] 00046-dot-tui-secret-status-refresh-v1.md — **PARKED to `dev/local/prds/hold/`** (cap_critical stall, cycle 2). Fix for issue #92 (`GitOps.status()` now runs the guarded `cfg secret hide -m` step before reading porcelain, mirroring `GitOps.commit()`). Cycle 1 rework landed clean (`a0f45b7`/`d654dc0`/`b6a8cb7`). Cycle 2 hit `rework_cap` 2 with an unresolved CRITICAL (`tests/tools/dot/test_tui_snapshots.py:57` mocked the OLD `GitOps.status()` 2-tuple contract, crashing all 10 dot snapshot tests with `ValueError: too many values to unpack`) plus 3 HIGH findings (StatusBar `height:1` hides the hide-error at 80 cols, quit guard fails open discarding `_hide_secrets()` errors, hide-error tests asserted the model string not rendered output) — full plan in `dev/local/reviews/00046-dot-tui-secret-status-refresh-v1-review-02.md`. **Since the park, 5 more commits landed on master addressing these** (`2e33a2d`/`53babe6`/`b0d089c`/`d71af1a`/`b66e9c9` — "keep TUI status readable when hiding secrets fails", "surface TUI hide failures in the status bar", docstring note) and CI is green on master as of 2026-08-15. Issue #92 is still OPEN on GitHub as of this catchup — unclear whether the cap_critical CRITICAL (snapshot-test mock contract) is actually fixed or only the 2 StatusBar HIGH findings were addressed outside the autopilot loop. **Needs a human check before un-parking**: verify `test_tui_snapshots.py` against the current `GitOps.status()` contract, then either close #92 or `mv dev/local/prds/hold/00046-dot-tui-secret-status-refresh-v1.md dev/local/prds/backlog/` to resume via autopilot's own review cycle.
- [x] 00047-updater-fail-loud-v1.md (2 cycles → done). `_reexec_or_exit` fails loud on re-exec `OSError` instead of silently `sys.exit(0)`ing; interactive-path upgrade timeout raised to 1800s (`_INTERACTIVE_UPGRADE_TIMEOUT`). Cycle 2 tail-swept 3 medium test-quality/mypy findings. 6 deferrals recorded (2 high scope-ambiguity, 4 low/medium out-of-surface) in `dev/local/autopilot/deferred/202608151500-deferred.json`.
- [x] 00048-fctracker-integrity-v1.md (2 cycles → done, converged with deferrals at `rework_cap`). CSV reader now rejects non-monotonic (oldest-first) order; command layer catches the reader's order-violation error plus overdraft/zero-amount/malformed-cell errors with human-readable messages and source-row numbering. Cycle 2 hit `rework_cap` 2 with 2 unresolved HIGHs recorded as cap-overflow deferrals in `dev/local/autopilot/deferred/202608151500-deferred.json`: (1) the `description`-cell guard from commit `670de3d` has no regression test; (2) a stray file (e.g. `.DS_Store`) in `transactions_dir` crashes both commands with a raw `NotADirectoryError` (pre-existing, outside this PRD's diff) — raise both at batch-end review.
- [x] 00050-zettel-scanner-error-surfacing-v1.md (2 cycles → done, converged with deferrals at `rework_cap`). `MarkdownZettelRepository.find_all` now surfaces the Rust scanner's `(results, errors)` tuple (warn-once via console) and the Python fallback isolates-and-reports non-mapping front/back matter instead of raising out of the whole scan; escaped Rich markup in bracketed filenames; moved the Rich import out of module scope (interface-agnostic-library invariant). Cycle 2 hit `rework_cap` 2 with 1 unresolved HIGH (non-string YAML mapping keys still escape `find_all`, pre-existing not a regression) recorded as cap-overflow deferral alongside 5 others in `dev/local/autopilot/deferred/202608151500-deferred.json` — first recommended item for a follow-up PRD, alongside 3 Rust-side deferrals from cycle 1.
- [x] 00052-decouple-pybase-from-click-v1.md (1 cycle → done). Importing `buvis.pybase.configuration` previously monkey-patched Click globally at module import time; now the patch installs lazily from `buvis_options` (task 1), updater output routes through the console adapter instead of `click.echo` (task 2), and `configuration/__init__` re-exports Click integration lazily via module `__getattr__` instead of eagerly (task 3). GAP → 00052 per AGENTS.md's "library stays interface-agnostic" invariant, now closed (flipped to HOLDS). Cycle 1 tail-swept 8 medium/low findings (tests + stale AGENTS.md marker); 1 settled deferral (pre-existing 52-line function, out of scope).
- [ ] 00053-dot-git-ops-unification-v1.md — **PARKED to `dev/local/prds/hold/`** (`task_premise_fail` stall, 2026-08-16). Unifies dot's three parallel git-op implementations (CLI `commands/{status,add,unstage,commit,push,pull,rm,delete}/`, TUI `tui/git_ops.py`'s 15-method `GitOps` class, and `tui/commands/{browse,secrets}.py`) behind one `DotGitService`; folds in the 00045 rm-safety and 00046 secret-status behavior. **11/12 tasks done and committed**: 1-3 built `dot/git/service.py::DotGitService`; 4-6 rewired CLI `status/add/unstage`, `commit/push/pull`, `rm/delete/encrypt`; 7 extracted `cli.py::_dotfiles_root()`; 8-9 retyped TUI `app.py`/screens to `DotGitService`; 10-11 routed TUI `browse.py`/`secrets.py` through the service (commits `b8d0f85d`..`4bfb4a59`). Task 12 (delete `tui/git_ops.py`, verify exit criteria) stalled on a false premise: its text assumed `tests/tools/dot/test_git_ops.py` was already deleted/renamed by tasks 2/3, but it still imports `dot.tui.git_ops.GitOps`; `test_git_service.py` already supersedes it (191 tests vs 60) but the task text explicitly forbade fixing this inline and mandated stop-and-report. **To resume**: `mv dev/local/prds/hold/00053-dot-git-ops-unification-v1.md dev/local/prds/backlog/` — a human (or a replan) needs to either delete the stale test file as part of task 12 or split it into its own task.
- [x] 00054-bim-serve-tui-convergence-v1.md (2 cycles → done). Routes bim's PATCH route, WebUI action handlers, and TUI create/edit through the existing command classes/use cases instead of ad-hoc writes: inline PATCH write → `UpdateZettelUseCase`/`CommandEditNote`; action handlers → `CommandResult.to_dict()` + mapped HTTP status (was 200-on-error); TUI create → `CommandCreateNote` (was bypassing required-answer validation); TUI `EditScreen._save`/`EditNoteApp._save` → surface `CommandResult` failures via new `notify_result` helper (was silently dropped). Cycle 2 found only Medium findings (no Critical/High); tail-swept 3 (one shared PATCH code path, `unwrapEnvelope` `res.ok` check, LinkWidget `aria-live`). One low deferral remains: manual WebUI failure smoke test (frontend has no test harness — human post-merge step the PRD itself declares).
- [ ] 00055-bim-cli-modularization-v1.md — **in progress**, selected 2026-08-17, 3/9 tasks done. Splits `src/tools/bim/cli.py` (772 lines, 13 commands, 52 hand-rolled `console.success/failure/panic` calls) into per-group self-registering Click modules mirroring the existing doc-rules registration pattern; replaces hand-rolled result rendering with `console.report_result`; splits `test_cli.py` to match. Sequenced after 00054 by design (avoids rewriting handlers 00054 was also touching) — precondition now satisfied. Tasks 1-3 done and committed: `doc_cli.py` (`95eb46c5`), `serve_cli.py` (`3aa00953`), `note_write_cli.py` (`ebe82189`). Task dependency graph: 1(done) → {2,3,4} (moves, parallel-safe in sequence) → 5 (verification checkpoint) and 6/7/8 (`report_result` swaps) → 9 (test-file split, last). Task 4 (`note_read_cli.py`) has its commit landed (`abb0a606`) but state still shows it `in_progress`, not `task-done` — a prior session's turn ended mid-task after the commit; `/work` resumes it (verify/finish, then mark done) rather than re-doing the extraction.
- [ ] 19 PRDs remain in `backlog/`, 00042/00046/00049/00053/00059/00069 parked in `hold/` — next batch PRD selects automatically.

Observations: `defer` CLI's deferred-file format is `{"batch_id","items":[...]}`, not a bare array — the on-disk `202608151500-deferred.json` had drifted to the legacy array shape and needed reshaping before `autopilot defer` would accept new appends (ValueError → exit 9).

### Batch 202605111417
- [x] 00038-pidash-bundled-hooks-v1.md (3 cycles + blind + doubt → done)
- [x] 00040-bim-doc-file-path-link-v1.md (2 cycles + blind + doubt → done)

Observations from PRD 00040:
- `_DoubleQuoted(str)` + module-level `yaml.SafeDumper.add_representer` is a clean pattern for forcing scalar style on a single key at serialisation time without affecting other yaml.safe_dump callers. The subclass is private (underscore-prefix, not in `__all__`), so the global representer registration has no blast radius.
- `urllib.parse.quote(p, safe="/~")` output charset is strict ASCII unreserved + `%XX`; no character it produces requires YAML escaping inside a double-quoted scalar. Long paths (~190 chars in the fixture) did not trigger PyYAML line-wrapping at default `width=80`, so realistic file_path values stay single-line.
- Blind reviewer flagged the pre-existing `html_static_path entry _static does not exist` sphinx warning as Important (spec criterion miss). It's actually a stale conf.py reference on master, unrelated to this PRD. Trivial future cleanup: `touch docs/source/_static/.gitkeep`.
- Spec success criteria that snapshot git history (`git log --oneline -2` shows feat+docs) are workflow-fragile inside autopilot — rework/cleanup commits inevitably land on top, invalidating the assertion. Prefer "the diff contains commits matching pattern X" framing in future PRDs.
- The `[Open PDF]` body-line removal forced a `test_promote.py` adjustment (anchor on H1 instead of body link). Reviewers will spot the +1 file count vs PRD's stated 11 staged files — autonomous_decisions log makes this auditable.

Observations from PRD 00038:
- Tasks 18/19 (live migration on the user's `~/.claude/hooks/`) were deferred to user. After this batch settles, run `pidash hooks install` on the dotfiles machine and delete the six legacy hook scripts from `~/.claude/hooks/`.
- New atomic-write helper `pidash.hooks.session.write_json_atomic(target, data)` is the canonical state.json/session-file writer for any future hook. Don't reintroduce `Path.write_text` on state.json — the shared-fate guarantee (tested in `test_set_attention.py::test_atomic_write_failure_does_not_corrupt_either_file`) is what protects autopilot progress.
- `pidash.hooks.session.SESSIONS_DIR` is the single source of truth; never re-export it from `tui.watcher` again (cycle 2's stale test deletion locks that down).
- CLI shape change: `pidash <path>` no longer accepts a bare positional. Use `pidash --project-path <path>` or `pidash tui <path>`. Documented in CHANGELOG/Changed and pidash.rst.
- Cycle 2 finding (`{"hooks": null}` slipping past the cycle-1 non-dict guard) was a Protocol B recurring-issue that auto-fixed cleanly; the predicate is now `if "hooks" in data and not isinstance(data["hooks"], dict)`. Worth recalling next time a `data.get(key) is not None` filter feels too generous.

### Recently shipped (last batch)
- Batch 202605101200 ✅ — 00037-bim-doc-audit.md (3 cycles + blind + doubt → done)
- Observations from 202605101200:
  - Cycle-3 hard-stop discipline works well: when reviewers' minor findings cluster around real but bounded improvements, escalating to user lets Bob pick the highest-value 4 of 5 instead of fighting consensus arithmetic.
  - Blind-reviewer Important findings overlapped 50% with cycle-1 autonomous decisions (OCR-confidence inert; watcher stub). Both still warranted action — fix the *symptom* (misleading stdout) while preserving the original rationale (limitation acknowledged).
  - Doubt review caught two genuine gaps the multi-reviewer cycles missed: (a) docs lagged the new JSON field, (b) no test pinned the field's serialization. Pattern: when a model gains a field, immediately add a `to_json_dict` key assertion AND a Sphinx-contract bullet.

Carried-forward reviewer + workflow observations:
- Reviewer Bob (codex / static-only) has been catching pre-existing defects that Alice/Diana miss because Bob's attention isn't anchored to the diff scope. When all 3 reviewers say "clean" but Bob is the only one running deep static reasoning, his 1/3 findings deserve closer scrutiny than `1/3 → low-priority`.
- Blind reviewer's "Important" findings tend to be hedged maintenance concerns ("not a bug per spec wording"); Phase 7's "Important → create [BLIND] tasks" can over-fire when the reviewer themselves dismisses the finding.
- Recurring pattern from 00035: model-symmetry tests let helper-level divergences ship undetected; parametrize consistency tests over real input combinations (e.g. `{date present, date None}`).

PRD 00037 archived context (bim doc audit):
- **Greenfield command.** Spec §9 (line 1017+) defines the audit table. No `audit` code exists yet anywhere under `src/tools/bim/commands/doc/`; the only mention is a comment in `state_db.py:181` noting that audit walks are read-only.
- **CLI surface.** New `@doc.command("audit")` registered in `src/tools/bim/cli.py`, alongside existing `ingest`, `promote`, and the `register_rules_subcommands(doc)` group. Lazy-import the command class inside the handler (project convention).
- **Sibling existing logic to reuse.** `commands/doc/shared/issuers.py` (registry + doc_types), `commands/doc/shared/naming.py` (canonical filename grammar), `commands/doc/shared/state_db.py` (sha256/last-match queries — read-only access path documented at L181), `commands/doc/shared/rules/engine.py` (rule validation, conflict detection, freshness — `bim doc rules validate` already exists under `commands/doc/rules/validate.py`). The audit's "rule engine" check should call into the same engine, not reimplement.
- **Zettel-existence check is per-issuer (PRD 00035 v1 layout).** `<vault>/<doc-subdir>/<issuer-slug>/<basename>.md`. Zettels at the legacy flat path (`<vault>/<doc-subdir>/<basename>.md`) must be reported as `legacy_layout_zettels`, not as `missing` — that list is the input contract for PRD 00036.
- **Output split.** Human-readable summary on stdout via `console`; structured JSON report at `<state_dir>/audit/<iso-timestamp>.json`. State dir comes from `settings.doc.paths.state_dir` (existing pattern; see promote/ingest for setting access).
- **Read-only invariant.** Never moves/deletes/rewrites. Failure modes report; they do not auto-heal. State.db reads only; no writes.
- **Out of scope (per PRD non-goals).** Auto-migration of legacy zettels (PRD 00036), auto-rewriting frontmatter mismatches (separate hardening PRD if needed), parallelization (sequential walk is fine for v1).
- **Watcher heartbeat in spec sample output.** Watcher itself is not yet implemented; either skip the heartbeat row in v1 or guard it ("watcher: not configured"). Flag during planning.
- **Audit + rule freshness coupling.** Spec lists "rule freshness (last 90 days)" under audit's rule-engine block. `rules engine` already tracks last-match per rule; reuse that, do not re-derive.
- **Docs.** New command must update `docs/source/tools/bim.rst` and `README.md` (per global `## Workflow reminders`).

### Recently shipped
- Batch 202605081200 ✅ — 00034 + 00035 (rule engine v1 + zettel-shape v1, shipped in v0.11.0/v0.11.1)
- 00034: 4 cycles, 6 rework tasks, 1 doubt FIX
- 00035: 5 cycles, 33 planned + 1 BLIND task + 3 doubt FIX edits. Blind reviewer caught a per-issuer-vs-legacy collision-check bug that all 5 review cycles missed (commits 996138c + f4103dc) — same defect class the audit must now report cleanly via `legacy_layout_zettels`.
- Batch 202605061124 ✅ — 00032-bim-doc-hardening
- Batch 202605042321 ✅ — 00029/00030/00031 (bim doc subsystem v1, shipped in v0.11.0)

## Related context

Topic: branch `master` + PRD 00055 title ("bim: split the cli.py god registry"). Repo-scope and portfolio-scope hits are both near-self-matches (00055's own PRD text, scores ~0.0154-0.0328), plus one cross-repo near-match (doogat/ddb PRD 00183 "split oversized modules round 2", a where-compiler module split — same shape of problem, different codebase, not directly reusable) — no prior review overlap surfaced. (00054's related-context note from the prior pass: repo/portfolio hits were near-self-matches plus 00042's title, scores ~0.0154-0.0164, reflecting 00054's dependency on 00042's confinement/token layer; superseded here since 00054 is now done and 00055 is the active PRD.)

Review harvest: `engram harvest dev/local/reviews/*.md dev/local/tmp/*review*.md` (re-run 2026-08-17) upserted 22 real review files including the new 00054 cycle 1/2 pair. The `dev/local/tmp/review-*` scratch files and the per-PRD audit renders still fail with "missing frontmatter" (expected — raw task-review scratch and non-zettel audit docs, not zettels).

`engram status --scope portfolio` (2026-08-17, re-checked post-task-4): memory stale=14, prd stale=1, transcripts stale=2/dead=5993, code stale=3, findings/discovery clean. Reported per the staleness-stamp rule (nonzero exit); not actioned this session (routine background drift across the whole portfolio, not gems-specific, not blocking).

## GitHub State (2026-08-17, after the PR sweep — current)

- **Master is GREEN at `e8c54185`.** Run 32042310720, all 19 jobs pass including
  `tools (ubuntu-latest, 3.12, dot)`, the canonical cell where snapshot tests actually run.
  The red described in the section below is fixed: `2284890e` aligned the snapshot mock to
  `DotGitService.status()`'s 2-tuple, `e8c54185` deleted `src/tools/dot/tui/git_ops.py` and
  `tests/tools/dot/test_git_ops.py` (completing 00053 task 12 — that PRD's only remaining
  blocker is now gone, so it is un-parkable from `hold/`).
- **Open PRs: 5 → 1.** Closed #120 (serde_yml, superseded by `5e9ad84`), #115 (mypy,
  superseded by #104), #116 (ocrmypdf, duplicate of #103), #131 (typescript 7 — blocked
  upstream: `@sveltejs/kit@2.70.2` pins `peerDependencies.typescript` to `^5.3.3 || ^6.0.0`,
  and `npm install typescript@7.0.2 --dry-run` only resolves by overriding that peer).
  **#103** (ocrmypdf v17) is the sole survivor: `@renovate rebase` requested, merge on green.
  Its risk is low — `bim doc` shells out to the `ocrmypdf` binary with long-stable flags and
  never imports the Python API or the `watcher` extra that v17 rewrote.
- **CI flake to expect**: run 32042310720's first attempt failed with HTTP 429 downloading
  `astral-sh/setup-uv`. Because `tools` gates on `lib`, a `lib` failure silently *skips* the
  whole `tools` matrix — a red `test` job can therefore hide the fact that tool tests never
  ran at all. `gh run rerun --failed` cleared it. Check job-level results, not just the rollup.
- **Frontend has no type-checking at all** (no `check` script, `vite build` transpiles via
  esbuild without checking, CI sets `BUVIS_SKIP_FRONTEND: "1"` and has no npm step). Deliberate
  per the 07-10 review, but it makes every frontend dep bump unvalidatable by construction.

## GitHub State (2026-08-17, at catchup + PR-merge planning, HEAD `816ee504` — superseded above)

- **Master CI: RED.** Run 32008200774 (Test, commit `816ee504`) — job `tools (ubuntu-latest, 3.12, dot)` fails `10 failed, 645 passed, 5 skipped, 3510 deselected, 1 xfailed`. Single root cause (the stale snapshot mock, see the header note). Every earlier "master CI green" line in this file predates it.
- **5 open PRs, all dependency bumps, and every branch is 200+ commits behind master** — so every "green" check on them ran against a base that no longer exists: #131 (206 behind), #120 (215), #116, #115 (CONFLICTING/DIRTY), #103 (212). Staleness verified against master's own pins:
  - #120 serde_yml 0.0.12→0.0.13 — **redundant**, `src/rust/Cargo.toml:14` already reads `serde_yml = "0.0.13"` (landed manually in `5e9ad84`). Close.
  - #115 mypy `<2,>=1.15`→`>=1.15,<3` — **redundant and weaker**, `pyproject.toml:65` already reads `mypy>=2.3,<3` (#104, merged 08-09). Close.
  - #116 ocrmypdf `>=16,<17`→`>=16,<18` — **superseded by #103**, which moves the same pin to `>=17,<18`. Close one of the two, keep #103.
  - #103 ocrmypdf `>=16,<17`→`>=17,<18` — the only dep bump with real content. Needs rebase onto green master.
  - #131 typescript 6.0.3→7.0.2 — **unvalidatable as-is.** `.github/workflows/test.yml:12` sets `BUVIS_SKIP_FRONTEND: "1"` globally and the workflow has no `npm ci` / `svelte-check` step, so CI never compiles the bim frontend; its green checks say nothing about TypeScript. Renovate also flagged its own artifact-update failure (lockfile not regenerated). TS 7 is the Go-port compiler — treat as a migration, not a bump.
- `origin/renovate/lock-file-maintenance` exists (updated 2026-08-17) with no open PR; #149 lock maintenance already merged as `ed76b88a`.
- Two merged-but-undeleted remote branches from 07-13 still not cleaned: `origin/build/bincode-3`, `origin/build/textual-9` (human-only, brush never pushes).

## GitHub State (2026-08-17, earlier pass — superseded above)

- **1 open issue**: #92 (dot TUI misses changed git-secret files until CLI `dot status` runs — this is PRD 00046, parked to `hold/` at rework_cap even though later commits on master look like they address it; see Active Work). Not closed — verify before closing. Unrelated to 00055 (bim CLI, not dot).
- **5 open PRs**, unchanged from the last refresh, all dependency bumps: #131 (typescript 6→7, renovate — artifact-update problem flagged by renovate itself, needs manual look), #120 (serde_yml 0.0.12→0.0.13, dependabot — **stale**, master already migrated to 0.0.13 manually in `5e9ad84`; this PR is now redundant/supersedable), #116 (ocrmypdf dev requirement), #115 (mypy dev requirement, `<2,>=1.15`→`>=1.15,<3` — #104 already merged mypy v2 as a direct commit, so this PR may also be stale), #103 (ocrmypdf runtime v17, renovate).
- **Latest release**: gems-v0.12.6 (2026-08-06). Unreleased-commit count on master not re-checked this pass (previously 12 per `gh`'s compare, before 00054's ~19 commits landed) — treat any figure as a release-diff signal, not a batch commit tally.
- **Master CI is GREEN** (Test + Deploy Documentation, last run 2026-08-17). Failure history unchanged: pre-existing 08-06 lint entry and July entries, all predating the 4ff15cd ruff-alignment fix, not fresh.
- Two merged-but-undeleted remote branches from 07-13 not re-checked this pass: `origin/build/bincode-3`, `origin/build/textual-9` (human-only cleanup, brush never pushes).

## Project Health

Working tree clean, master `abb0a606` (PRD 00041/00043/00044/00045/00047/00048/00050/00052/00054 done, PRD 00042/00046/00053 parked to `hold/`, plus 00055 tasks 1-3 and task 4's commit), nothing unpushed beyond the batch's own commits. Local suite/mypy not re-run this catchup pass — master CI is green as of 2026-08-17, so treat that as the current confirmed-green baseline. Batch 202608151500 (launched 2026-08-15) continues: `00041`/`00043`/`00044`/`00045`/`00047`/`00048`/`00050`/`00052`/`00054` done, `00042`/`00046`/`00053` parked (resumable from `hold/`), `00055` (bim-cli-modularization) in progress, 3/9 tasks done, task 4 committed but not yet marked done (resume point). PRDs `00041`-`00061` are the original evolution roadmap (numbered = execution order); 00047/00048/00050 are outside that numbered roadmap — independently-triaged backlog PRDs. Tail tools (netscan/vuc/puc/morph/zseq/outlookctl/fren/pinger) are maintenance-only — all demonstrated demand is in bim/dot/sysup (pidash is being retired via 00071).

## Project Memories

- bincode v3 dead after doxxing - stay on v2, close any v3 upgrade PRs
