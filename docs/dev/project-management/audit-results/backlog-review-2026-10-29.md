# Backlog review - buvis/gems - 2026-10-29

Verdict: GO (both Blocking findings fixed in place during the apply pass; zero open, no reshapes)

Target: `docs/dev/project-management/prds/backlog/` (five PRDs specced from intake 00107 on 2026-10-29, commit 3caa64c9). `wip/` absent, `hold/` empty, `done/` ends at 00108. Law loaded from `~/.agents/skills/create-prd/SKILL.md` and `assets/standard.md`; budget and tier rules from `autopilot:plan-tasks` steps 4.5 to 4.7 (plugin 0.10.0).

Mechanical checks:

- Hygiene: five `NNNNN-slug-v1.md` files, nothing else in `backlog/`. Sequence numbers unique across `prds/**` and `intake/*/` (00107 is shared by the intake item and its first PRD by create-prd's rule).
- Citation resolution (`check_links.py --root . --json`): zero findings under `prds/backlog/` or `prds/wip/`. The 20-odd repo-wide hits are in `research/`, `designs/`, `reviews/` and older audit results, outside this gate's scope.
- Grounding resolution (`ground_prd.py --root . --json prds/backlog`): every row `ok` or `declared-new`; zero `missing`, `unresolved` or `unverified`.
- Lens D manual pass (`rg` against the repo): every cited line, symbol and premise verified (runner.py:44 excludes pass-through, `extra="forbid"` on `BackupInstance`, the `resolved global excludes for` header, `inputs` = source/out/engine, the bundled list containing `build dist out target coverage .cache .npm`, tar_archive.py:107-108, both `os.replace` sites, the `except BaseException` cleanup, `_expand_stamp` at :373, `subprocess.run` at :340, `test_missing_source_fails_cleanly` once, the `StepResult("a", False, "a failed: source not found")` fixture, `Capability` protocol with one registered capability, `console.status` returning a rich `Status`, no existing `--quiet` in `buvis_options`, `test_invariants.py` scanning config/runner/capabilities/shared but not cli.py). The backup code is unchanged since 1c68155f (2026-09-27).

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00107 | backup-per-instance-excludes-v1 | standard | 128 | backup config, runner, cli | none | READY (was FIX, B2 applied) |
| 00109 | backup-bundle-items-and-skip-outcomes-v1 | standard | 171 | backup step_result, tar_archive, cli | 00107 | READY |
| 00110 | backup-plan-preview-and-output-resolution-v1 | standard | 148 | backup step_result, capabilities protocol, runner, cli | 00109 | READY |
| 00111 | backup-parallel-jobs-and-cancellation-v1 | standard | 135 | backup tar_archive, runner, cli | 00110 | READY (was FIX, B1 applied) |
| 00112 | backup-live-progress-and-quiet-v1 | standard | 150 | backup step_result, tar_archive, runner, cli | 00110, 00111 | READY |

Frontmatter after the apply pass: `catchup: skip` on all five; `design: skip` on 00107, 00109, 00110 and `design: run` on 00111, 00112; `default_model` sonnet on 00107 and 00110, opus on 00109, 00111, 00112, each with a rationale line. All recognized keys and values.

## Findings

### Blocking

- [00111] H goal alignment / B executability: Feature `--jobs` specifies `click.IntRange(min=1)` and the Phase 2 task's acceptance requires "`--jobs 0` exiting 2 (click usage error)". AGENTS.md's Click argument validation rule forbids parse-time validators (`IntRange` is named) because they bypass the buvis console; validation belongs in the callback with a console message and exit 1, which is how `--for requires --show-excludes` already works (`src/tools/backup/cli.py:201-203`). -> fails as: rework thrash (every reviewer reads AGENTS.md and flags it; the acceptance locks the violation in so the implementor cannot comply with both). Fix: `--jobs` becomes a plain `int` option with default 3; the callback rejects `jobs < 1` with `console.failure("--jobs must be at least 1")` and `raise SystemExit(1)`; the task acceptance asserts exit 1 and that message.
- [00107] B executability: Feature "Wire into run and inspection", Behavior: "`--show-excludes` header stays `resolved global excludes for '<name>':` replaced by `resolved excludes for '<name>':`". "Stays" and "replaced by" contradict; a test or implementation can pin either string. -> fails as: wrong-TDD lock-in (the header is the one observable the `-k show_excludes` test can assert beyond list content). Fix: "The `--show-excludes` header changes from `resolved global excludes for '<name>':` to `resolved excludes for '<name>':`."

### Non-blocking

- [00111] B: the cancel loop recipe "`process.communicate(input=..., timeout=0.2)` retries" raises `ValueError("Cannot send input after starting communication")` on the second call. Fix: pass `input` on the first call only; retries call `communicate(timeout=0.2)` without it. Caught at task level by the stub-tar test, so not Blocking, but the recipe should not mislead the implementor.
- [00107, 00109, 00110, 00112] A: Module blocks without an `Exports` line (`standard.md` lists it): 00107 "runner and cli", 00109 "cli", 00110 "cli", 00112 "tar_archive", "runner", "cli". Fix: add `Exports: none new` or the touched function names. Parsers read headings, not these bullets; cosmetic.
- [00109, 00110, 00111] E cross-invalidation: Problem Statements cite line numbers (`tar_archive.py:107`, `:108`, `:373`, `:340`, `runner.py:31`) that shift as the earlier PRDs land, and `catchup: skip` means no session re-grounds them. The symbols stay valid and the lines are context, not premises. Accepted as is; a later `ground_prd` run on `wip/` would read them as `missing`.
- [00111] B: the interrupt exit code 130 names no mechanism. `cli.py` already uses `raise SystemExit(n)` and `test_invariants.py` does not scan `cli.py`, so `raise SystemExit(130)` is the unambiguous reading. Accepted as is.

### Questions

- [00111, 00112] B frontmatter: both carry `design: skip` although 00111 is concurrency, cancellation and subprocess lifecycle and 00112 crosses worker threads into the calling thread (both `default_model: opus` for exactly that reason), and the discovery's Q12 answer said the parallelism PRD "gets its own design pass". Options: `design: run` on 00111 and 00112; `design: run` on 00111 only; keep `skip` on both.

## Reshapes

None. Sizes 127 to 170 lines, three phases each, one subsystem each, consecutive numbers, every dependency points at a lower number (00107 < 00109 < 00110 < 00111 < 00112). Same-file edits across the five (tar_archive.py, runner.py, cli.py, step_result.py) build on each other with compatible end shapes.

## Gaps

- Producer/consumer chain closed: 00110 consumes 00109's `items` validation and skip state; 00111 consumes 00110's duplicate rejection and run-wide `now`; 00112 consumes 00111's pool and 00110's `--plan`.
- No half-migration: `StepResult` gains `skipped` (00109) and `PlanEntry`/`ProgressEvent` are additive records; `Capability` gains `plan` with one registered implementation.
- Every PRD updates `docs/source/tools/backup.rst` and `CHANGELOG.md`; no cleanup debt left behind. Out of scope by the discovery's own decision: per-archive log files and a sandbox flag.
- No strategic gap in this set; no `/assess-evolution` recommendation beyond the standing roadmap.

## End state after this batch

`backup` keeps its engine guarantees (atomic publication, `chmod 600`, gzip, links as links, layered excludes) and gains an operator-grade run loop: per-instance exclude control, bundles of items under one base with tolerant presence and explicit skips, a cheap `--plan` table with one timestamp per run and duplicate-output rejection, up to three parallel archives with clean Ctrl-C, and a live status line that stays quiet off a terminal. The Runner stays the single execution seam and the CLI the only console writer. What it still lacks is a non-CLI interface (manifest says CLI only, by design) and no-clobber, which the user dropped on 2026-10-29 in favor of replace-after-complete.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00109, 00110, 00111, 00112 | `catchup: run` instead of `skip` | all four edit production code; the batch cache makes a second catchup nearly free and the session gets the capsule's invariants (console-only output, atomic persistence) instead of relying on PRD prose |
| 00111, 00112 | `design: run` | see Questions; opus-tier concurrency work with no design doc |
| 00109 | `design: run` | invents the item-selection algorithm and the skip/exit contract three later PRDs consume |

## Decisions applied

Walked 2026-10-29. The two Blocking findings and the two Non-blocking text fixes each had one clearly best edit and were applied under the user's standing authorization for routine reversible edits; the design flag was the one question put to the user.

1. B1 [00111] applied: Feature `--jobs` Inputs now reads a plain `int` option with default 3, rejected below 1 in the callback with `console.failure("--jobs must be at least 1")` and `raise SystemExit(1)`; the Phase 2 task acceptance asserts `--jobs 0` exits 1 with that message.
2. B2 [00107] applied: the header sentence now reads "changes from `resolved global excludes for '<name>':` to `resolved excludes for '<name>':`".
3. N1 [00111] applied: the cancel loop passes `input=` on the first `communicate` call only; retries call `communicate(timeout=0.2)`.
4. N3 [00107, 00109, 00110, 00112] applied: every Module block now carries an `Exports` line (`none new`, naming the gained kwarg where one exists).
5. N5 [00111] applied as a clarity edit: exit 130 is `raise SystemExit(130)`, the pattern `cli.py` already uses.
6. Q1 [00111, 00112] user chose `design: run` on both; applied.
7. Not applied, kept as suggestions: `catchup: run` on 00109 to 00112 and `design: run` on 00109. The author set those deliberately and nobody asked to change them.
8. Accepted as is: line-number citations in Problem Statements that will drift as earlier PRDs land.

Re-checks after the edits: the heading walk of all five PRDs matches `standard.md` top to bottom; `ground_prd.py` on `backlog/` returns zero rows outside `ok` and `declared-new`; `check_links.py` returns zero findings under `prds/backlog/` or `prds/wip/`.

Gate honesty: every lens A to H ran inline (five PRDs, no subagent dispatch needed); no lens skipped; both scripts present and run twice (before and after the edits).
