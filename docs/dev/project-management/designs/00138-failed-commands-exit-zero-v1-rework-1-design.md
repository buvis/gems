# Rework design: 00138-failed-commands-exit-zero-v1, cycle 1

Source review: docs/dev/project-management/reviews/00138-failed-commands-exit-zero-v1-review-1.md (head_sha e842a6f6c7fbffb2b7860ce0448d71c9e7f3e2ce)

## Architecture fit

Prior fix: none - there was no prior rework fix.

The cycle-1 work range `4afffe6db744fc2df8fc39102cc82844ce2d0028..e842a6f6c7fbffb2b7860ce0448d71c9e7f3e2ce`
added the shared helper correctly and then under-applied it. `git diff --stat` over that
range shows `src/tools/dot/cli.py | 1 +` and `src/tools/postup/adapters/cli.py | 2 +-`:
one converted call site each, against 14 `report_result` calls in `dot/cli.py` and 6 in
`postup/adapters/cli.py`. Every other tool (fren, zseq, muc, puc, vuc, morph, netscan,
klyreon, bim) was converted in full.

Both CRITICAL rows this design closes were **exposed, not introduced**, by the cycle-1
fix. The exit-0-on-failure behaviour is the pre-existing defect the PRD exists to remove;
the fix removed it everywhere except the two tools the PRD names by name. The planning
gap is traceable: task 2 said "Do not touch any other command in either CLI file", and
task 3's file list omitted `src/tools/dot/cli.py` and `src/tools/postup/adapters/cli.py`
entirely, so no task owned the remaining call sites.

The 🔴 rows, verbatim:

- **R2** `postup brief`, the PRD's own evidence command, still exits 0 on failure. The
  conversion went onto the bare `postup` default path in `cli()`, not the `brief`
  subcommand, whose `console.report_result(result)` call has no `exit_on_failure=True`.
  The new `TestBarePostupExitCode` tests invoke `cli, []` only, so nothing covers
  `["brief"]`, and the PRD success metric "`postup brief` exits non-zero" is unmet.
- **R3** The PRD metric "No tool's CLI exits 0 after printing a failure from
  `report_result`" is unmet for dot and postup. These calls still lack
  `exit_on_failure`: postup `collect` (:49), `enrich` (:60), `tui` (:87), `serve` (:106);
  dot `materialize` (:64), `setup` (:82), `add` (:98), `encrypt` (:107), `rm` (:116),
  `delete` (:125), `pull` (:165), `commit` (:174), `run` (:187), `unstage` (:196),
  `push` (:204), `localize` (:221, :232).

This work lands entirely in the CLI adapter layer (`src/tools/<tool>/cli.py` and
`src/tools/postup/adapters/cli.py`). The library helper
`ConsoleAdapter.report_result` is already correct and is **not** touched. That keeps the
repo's "CLI layer inspects `CommandResult` and renders it; command classes never exit"
invariant intact.

## Module placement

Edits to existing files only. No new source files.

| File | Change |
|------|--------|
| `src/tools/postup/adapters/cli.py` | add `exit_on_failure=True` to the `report_result` calls in `brief` (:73), `collect` (:49), `enrich` (:60), `tui` (:87), `serve` (:106) |
| `src/tools/dot/cli.py` | add `exit_on_failure=True` to the `report_result` calls in `materialize` (:64), `setup` (:82), `add` (:98), `encrypt` (:107), `rm` (:116), `delete` (:125), `pull` (:165), `commit` (:174), `run` (:187), `unstage` (:196), `push` (:204), `localize` (:221, :232); replace the bare `console.failure(plan.error); return` at :141-143 with a terminating report |
| `CHANGELOG.md` | rewrite the existing `**console**` bullet so it no longer overclaims, and name both deliberate exit-0 exceptions |
| `docs/source/tools/dot.rst` | reword the `dot status` paragraph: drop the "this PRD" reference and the em dash |

New test files:

| File | Covers |
|------|--------|
| `tests/tools/postup/adapters/test_cli_brief_exit_code.py` (extend) | the `brief` **subcommand** via `invoke(cli, ["brief"])`, plus `collect`, `enrich`, `tui`, `serve` |
| `tests/tools/dot/test_cli_exit_code.py` (new) | each converted `dot` subcommand, and the `dot pull` rescue-plan error path |

Existing tests that **must change in the same commit** as the conversion, because they
assert the old exit-0-on-failure behaviour:

| File | Change |
|------|--------|
| `tests/tools/dot/test_dot_commands.py` | every case that feeds a `success=False` `CommandResult` to a converted command must assert `exit_code != 0`. Confirmed stale: `test_pull_failure` (:86-91) mocks `CommandPull.execute` to fail and asserts `exit_code == 0`. The same pattern recurs for `commit`, `unstage`, `push` and `rm`. **`test_pull_failure` needs more than a flipped assertion** - see the note below. |
| `tests/tools/dot/test_pull.py`, `test_push.py`, `test_localize.py`, `tests/tools/postup/adapters/test_cli.py` | audit for the same shape: a service-level failure that now surfaces through a converted `report_result` site. |

**Mandatory sweep before the task is done**, not an optional check. A literal
`rg -n 'success=False' tests/tools/dot tests/tools/postup` is the starting point, **not
the proof of coverage**: it misses `CommandResult(False)` passed positionally, spaced
assignments, failures built in a fixture, and `MagicMock`-configured failures where no
literal appears at all. So the sweep is three steps, all required:

1. `rg -n 'success=False' tests/tools/dot tests/tools/postup` - the literal hits.
2. `rg -n 'exit_code' tests/tools/dot tests/tools/postup` - every exit-code assertion in
   both trees; for each, decide whether its command is now converted and whether the
   result it feeds is a failure.
3. Run the narrow gate and **adjudicate every failure it exposes**: a red test here is
   either a stale assertion to update or a real regression. Do not update an assertion
   without deciding which it is.

**`test_pull_failure` is a false positive waiting to happen.** It mocks `CommandPull` but
configures only `execute.return_value` (`tests/tools/dot/test_dot_commands.py:86-91`);
only the *other* pull test configures `plan` (:99 `plan.return_value = RescuePlan()`). So
its unconfigured `plan()` returns a `MagicMock` whose `.error` is **truthy**, and
`dot/cli.py:pull` takes the plan-error branch and returns before ever calling `execute`.
Today that still yields exit 0, so the stale assertion passes for the wrong reason. After
the rewrite, merely flipping it to `exit_code != 0` would *also* pass for the wrong
reason - via the plan-error branch, still never testing the `execute` failure the test is
named for. The fix is two tests:

- `test_pull_failure`: configure `plan.return_value = RescuePlan()` (so `error` is `None`
  and there are no collisions), keep the failing `execute`, assert `exit_code != 0`, and
  assert `execute` **was** called.
- a separate plan-error test: set `plan.return_value = RescuePlan(error="...")`, assert
  `exit_code != 0`, the error text in the output, and that `execute` was **never** called.

Cycle 1 hit this exact wall and spent a separate commit
(`cdc5c413 test(cli): update stale exit-code-0 failure assertions to match exit_on_failure`)
on it after the fact. Converting the call sites without this sweep turns the suite red on
work that is otherwise correct, and a task owner reading only the conversion contract has
no mandate to touch these files. That mandate is this row.

## Interfaces & contracts

No signature changes anywhere. The only contract is the call shape at each site and the
existing helper's semantics, restated here so a task owner needs nothing else.

**Existing helper, unchanged** (`src/lib/buvis/pybase/adapters/console/console.py`):

```python
def report_result(
    self: ConsoleAdapter,
    result: CommandResult,
    *,
    success_msg: str | None = None,
    failure_msg: str = "Failed",
    on_success: Callable[[CommandResult], None] | None = None,
    on_failure: Callable[[CommandResult], None] | None = None,
    literal: bool = False,
    exit_on_failure: bool = False,
) -> None
```

Semantics that bind this rework: when `result.success` is `False` and
`exit_on_failure` is `True`, `report_result` calls `sys.exit(1)` **after** the failure
output (the `on_failure` callback, or the default `emit`). The exit decision keys off
`result.success`, never the truthiness of `result.error`. A successful result never
exits, whatever `exit_on_failure` says.

### Closes: R2 - `postup brief` still exits 0 on failure

`src/tools/postup/adapters/cli.py`, in `brief`, the terminal report becomes exactly:

```python
    console.report_result(result, exit_on_failure=True)
```

The `if result.success and result.metadata.get("text"): console.print(...)` line above it
is unchanged and still runs first. The bare-`postup` path in `cli()` at :36 already
carries `exit_on_failure=True` and is not edited.

### Closes: R3 - 18 dot and postup callers still exit 0 on failure

Every site listed in `## Module placement` gains `exit_on_failure=True` as an additional
keyword argument to its existing `console.report_result(...)` call. No other argument at
any site changes, and no site's surrounding control flow changes. Two shapes occur:

```python
    # bare terminal report
    console.report_result(cmd.execute(), exit_on_failure=True)

    # terminal report that already passes a callback or `literal`
    console.report_result(
        result,
        on_failure=lambda r: console.failure(r.error or "Failed", details=r.metadata.get("details")),
        exit_on_failure=True,
    )
```

`dot pull`'s rescue-plan error path at `src/tools/dot/cli.py:141-143` is the one site that
does not currently route through `report_result` at all. It becomes:

```python
    if plan.error:
        console.report_result(CommandResult(success=False, error=plan.error), exit_on_failure=True)
        return
```

`src/tools/dot/cli.py` does **not** currently import `CommandResult`, so this site also
adds it **at module scope, beside the existing `buvis.pybase` imports at
`src/tools/dot/cli.py:8`**:

```python
from buvis.pybase.result import CommandResult
```

Module scope, not a lazy in-handler import: `dot/cli.py` lazy-imports every *command
class* to keep optional dependencies out of startup, but `CommandResult` is a plain
dataclass with no heavy dependencies, and `src/tools/muc/cli.py:8` already imports it
exactly this way for its aggregate report at `muc/cli.py:91`.

The `return` after the exiting call stays as **defence in depth**, not because a type
checker needs it: `report_result` is annotated `-> None`, not `NoReturn`, so no checker
treats the next line as unreachable and the `return` buys nothing statically. It buys
this: if the `exit_on_failure` argument is ever dropped at this site, the handler still
stops before the collision and passphrase work below instead of pulling on a known-bad
plan. This is **not** the R1 anti-pattern. R1 deletes a duplicated *exit*
(`if not result.success: ctx.exit(1)`) that re-does what `report_result` just did; this
`return` guards a bypass path and performs no exit of its own.

### Not a finding: `muc tidy` cannot print ✘ and exit 0

Dispatch 1 raised this as a blocker, arguing that because
`src/tools/muc/commands/tidy/tidy.py:22-23` hardcodes `success=True`, a failed step could
print ` ✘ ` at `src/tools/muc/cli.py:89` while the aggregate exits 0, leaving the PRD
metric unmet. **The premise is false, and the design does not change `tidy.py`.**

Every `DirTree` step helper constructs its result as `success=True` and never sets
`success=False`:

- `src/tools/muc/shared/dir_tree/merge_mac_metadata.py:120`
- `src/tools/muc/shared/dir_tree/lowercase_file_extensions.py:19`
- `src/tools/muc/shared/dir_tree/rename_equivalent_extensions.py:30`
- `src/tools/muc/shared/dir_tree/delete_by_extension.py:20`
- `src/tools/muc/shared/dir_tree/remove_empty_directories.py:19`
- `src/tools/muc/shared/dir_tree/dir_tree.py:100`

A recoverable filesystem failure is appended to `result.warnings` instead, e.g.
`delete_by_extension.py:29`:

```python
            result.warnings.append(f"Could not remove extra file {file_path}: {exc}")
```

`report_result` prints ` ✘ ` only on the `not result.success` branch, so a step result
whose `success` is always `True` can never produce a ` ✘ ` line. `muc tidy` therefore
never prints a failure line and exits 0, and the PRD metric holds for it as written. This
is also the decided design, already shipped and recorded in `CHANGELOG.md:50`: tidy
"reports cleanup actions and recoverable failures through the standard console ...
Warnings keep exit status 0."

Two consequences, both deliberate:

- **`tidy.py` is NOT edited.** `success=all(result.success for result in results)` would
  be dead code: no step can make the `all(...)` false, so the expression is a constant
  `True` dressed up as a computation. Writing it would add an unreachable branch of
  exactly the kind R1 is deleting elsewhere in this cycle.
- **R7 stays deferred, correctly.** Alice's R7 observed that the aggregate's
  `exit_on_failure=True` can never fire in production. That is true and benign: it is a
  defensive guard on a terminal report, and the only way to make it fire is to change
  tidy's step model from "warn and continue" to "fail", which is a product decision the
  PRD did not ask for. The cycle-1 ledger entry deferring R7 stands.

**Deliberate exit-0 cases, to be recorded and NOT converted** (R5's deliverable):

1. `src/tools/muc/cli.py:89` - the per-step `console.report_result(step, literal=True)`
   loop inside `tidy`. Each step is reported and the command continues to the next step,
   and the terminal aggregate call at :90-94 already carries `exit_on_failure=True`. The
   loop stays non-exiting by design: a step's problems are warnings, not failures (see
   "Not a finding: `muc tidy`" above), and a first step's trouble must not hide the
   remaining steps' output.
2. `src/tools/bim/doc_cli.py:315` - `_report_doc_result` prints `console.failure` and
   returns on `success=False` unless its `strict` flag is set. It does not route through
   `report_result`. Two call sites expose `--strict` and so are opt-in exits
   (`doc ingest` :94, `doc promote` :157), but `doc triage --approve` (:298) calls it with
   **no** `strict` argument and offers no flag, so that command prints a failure and exits
   0 with no opt-out available to a script. Record :298 as an unconditional exit-0 surface
   and a follow-up, not as a strict-gated one.

Nothing else in `src/tools/` is a deliberate exit-0 case. `rg 'report_result' src/tools/`
also matches `src/tools/klyreon/commands/assets.py:4` and
`src/tools/postup/commands/enrich/enrich.py:14`, but both are docstring prose about the
CLI layer rendering the result, not call sites.

**The durable home for this list is `CHANGELOG.md`** - tracked, user-facing, and already
the artifact the PRD asks for. Not a completion report, which is not a tracked artifact.
The CHANGELOG bullet below names both exceptions; this design section is the engineering
record behind it.

### Closes: nothing - supporting corrections carried in the same rework

`CHANGELOG.md:52`: the bullet currently claims "CLI commands now exit non-zero when their
command fails" under `**console**`. That stays false as a blanket claim even after this
rework, because the `bim doc` family reports through `_report_doc_result` rather than
`report_result`. So the fix both **narrows** the claim to the PRD's own scope - failures
rendered through `report_result` - and names the exceptions:

```markdown
- **console**: a CLI command whose failure is reported through `report_result` now exits non-zero, instead of always exiting 0 after printing a ` ✘ ` failure line. `muc tidy` is unchanged: it reports its cleanup results in step order, and recoverable filesystem problems stay warnings that keep exit status 0. The `bim doc` subcommands keep their own behaviour too: `ingest` and `promote` exit non-zero only with `--strict`, and `triage --approve` always exits 0. Scripts, hooks, or cron jobs that relied on the old exit-0-after-failure behavior will now see non-zero exits.
```

The claim is scoped to failures rendered through `report_result`, which is the PRD's own
success metric, rather than to "CLI commands" in general: the `bim doc` family reports
through `_report_doc_result` and is out of that scope, so a blanket claim would be false
for three of its subcommands.

`docs/source/tools/dot.rst:129`: drop "this PRD" and the em dash.

```rst
``dot status`` keeps hiding (re-encrypting) secrets on every run, with no flag
to disable it. That protection stays on by design. ``dot status`` now exits
non-zero if hiding secrets, or any other part of the status report, fails,
instead of always exiting 0 after printing a failure.
```

## Data flow

Unchanged in every case but one. A command class builds a `CommandResult`; the CLI handler
hands it to `console.report_result`, which prints the info, warning, success or failure
lines and now terminates the process with status 1 when the result failed. No command
class learns about exit codes, so the layering invariant holds.

The single flow change is `dot pull`: a rescue-plan error previously printed through
`console.failure` and fell out of the handler with status 0. It now travels the same
`CommandResult` path as every other failure, so the plan error and an execute error leave
the process in the same state.

## Reuse inventory

- `ConsoleAdapter.report_result(..., exit_on_failure=True)` -
  `src/lib/buvis/pybase/adapters/console/console.py:306`. The shared helper this PRD
  added. Already used by 9 tools; this rework applies it to the remaining two. Nothing new
  is written.
- `ConsoleAdapter.panic(message, details=None)` -
  `src/lib/buvis/pybase/adapters/console/console.py:124`. Prints a failure line and calls
  `sys.exit(1)`. Already used by `dot setup` (:76) and `dot localize` (:213) for argument
  errors, and by `console.require_import` (:309) for missing extras. Those sites already
  exit non-zero and need no change; this entry records why they are **not** in the edit
  list.
- `CommandResult(success=..., error=...)` - `buvis.pybase.result`. Used at
  `src/tools/muc/cli.py:91` to wrap an aggregate outcome for `report_result`. Reused
  verbatim for the `dot pull` plan-error path rather than adding a second failure-reporting
  idiom.
- `click.testing.CliRunner` - already the per-tool exit-code test idiom in
  `tests/tools/**/test_*exit_code*.py` (16 such files exist after cycle 1). The new dot
  tests follow `tests/tools/dot/test_status_exit_code.py` exactly.
- Greps run for the sweep: `rg 'report_result' src/tools/dot/cli.py src/tools/postup/adapters/cli.py`
  (20 hits, the conversion target list); `rg 'console\.(panic|failure|require_import)|ctx\.exit|sys\.exit|raise SystemExit' src/tools/dot/cli.py src/tools/postup/adapters/cli.py`
  (7 hits, proving `dot/cli.py:142` is the only non-exiting failure path in the two files);
  `rg 'exit_on_failure' --files-with-matches src/ tests/` (16 files, the already-converted
  set, which proves the pattern is present rather than absent). `~/.claude/rules-library/rationalizations.md`
  was not consulted; the sweep used the verb/noun pairs exit/terminate/status and
  result/outcome/code directly.

## Alternatives considered

1. **Convert every remaining call site plus the one bypassing path (chosen).** Smallest
   change that makes both PRD success metrics true. The exact scope, one number used
   everywhere in this doc: **18 `report_result` conversions** (postup 5 at :49, :60, :73,
   :87, :106; dot 13 at :64, :82, :98, :107, :116, :125, :165, :174, :187, :196, :204,
   :221, :232 — the file holds 14 `report_result` calls, of which :51 `status` is already
   converted) and **1 rewritten bypass branch** (`dot pull` :141-143) = **19 edited
   sites**. Two deliberate exit-0 cases are recorded. No signature change, no
   control-flow change outside the `dot pull` branch, and no command-class change at all
   — `muc/commands/tidy/tidy.py` is deliberately untouched (see
   `## Interfaces & contracts` → "Not a finding: `muc tidy`").
2. **Smallest-diff version: convert `postup brief` only.** Closes R2 and leaves R3 open.
   Rejected because R3 is the PRD's headline success metric, not a nice-to-have, and
   because the unconverted set is exactly the destructive commands (`dot push`, `commit`,
   `delete`, `rm`) where a wrong exit code does the most damage in a hook or cron job.
   This option is strictly smaller and strictly insufficient.
3. **Flip the helper's default to `exit_on_failure=True` and opt out where needed.**
   Tempting: it would make "no `report_result` caller exits 0 after a printed failure"
   true by construction and keep future call sites correct without anyone remembering the
   flag. The opt-out would be exactly one site, `muc tidy`'s per-step loop; `bim doc` is
   unaffected either way, since it reports through `_report_doc_result` and never reaches
   this helper.
   Rejected for this rework. `report_result` is library code in
   `src/lib/buvis/pybase/`, reachable by the TUI, the API and the WebUI adapters, and a
   default that calls `sys.exit(1)` would terminate a long-lived server process on a single
   failed action. The chosen option costs 18 one-argument edits plus two small code edits,
   and buys a blast radius
   confined to the CLI layer. If the flag is later forgotten at a new call site, the
   failure mode is the old exit-0 bug at one command, not a killed server.

What option 1's extra size over option 2 buys: the PRD's second success metric, and
correct exit status on the five `dot` commands that mutate the dotfiles repo.

## Risks & edge cases

- **Scripts that relied on exit 0.** The PRD names this risk and the CHANGELOG records it.
  `dot pull`'s plan-error path and the 18 converted sites all change observable exit status.
  This is the intended behaviour change, not a regression.
- **`dot pull` partially completes.** The plan error is raised before any mutation, so
  exiting there is strictly safer than the current silent `return`. The later
  `cmd.execute(...)` report at :165 also becomes terminating, which is correct: a failed
  pull must not look like a success.
- **A non-terminal `report_result` call misread as terminal.** `muc tidy`'s per-step loop
  is the only non-terminal call in `src/tools/`, and it lives in
  `src/tools/muc/cli.py` - **neither** file under edit here contains a loop, so no site in
  this rework can be misread that way. The risk is in the *recording* deliverable, not the
  code: if the exit-0 list is incomplete, R5 recurs. The list in
  `## Interfaces & contracts` is exhaustive for `src/tools/`.
- **`exit_on_failure` plus an existing `ctx.exit(1)`.** Not an issue in these two files
  (neither uses `ctx.exit`), but it is the live defect R1 reports in bim and klyreon. The
  R1 task removes those now-unreachable branches; this design must not add any new one, so
  no site here gains a post-report success check.
- **Likely next changes, and whether this design boxes them in.** (a) Giving the TUI, API
  or WebUI adapters the same failure-to-status mapping: unaffected, because the exit lives
  in the CLI layer and `report_result`'s default stays `False`. (b) A `--quiet` or
  machine-readable output mode: unaffected, the exit decision is independent of rendering.
  (c) Deriving `muc tidy`'s aggregate success from its steps (R7, deferred this cycle):
  unaffected, since the aggregate site already carries the flag and only the
  `CommandResult` fed to it would change.
- **`dot run` reports 1, never the wrapped command's own status.** `dot run` is an
  arbitrary-git passthrough; `src/tools/dot/commands/run/run.py:32` returns
  `CommandResult(success=False, error=err)` carrying no exit code, and `report_result`'s
  `sys.exit(1)` is fixed. A caller cannot tell git's 1 from its 128. Accepted for this
  PRD: the status was 0 before, so callers could not read it at all, and "non-zero on
  failure" is the metric. Propagating the underlying status is a follow-up, not this
  rework.
- **`dot materialize --hook` turning non-zero does not break git hooks.** The generated
  hook runs `subprocess.run([dot, "materialize", "--hook"], check=False, ...)` and then
  `sys.exit(0)` (`src/tools/dot/hostlinks/hooks.py:25-26`), so a non-zero materialize
  cannot fail a commit.
- **`postup collect`'s documented "always exits successfully".** `docs/source/tools/postup.rst:29-34`
  states that a repository whose data cannot be gathered degrades into that repo's
  `errors` list and a warning, and that the run "never crashes and always exits
  successfully as long as at least one repository was discovered". Converting `collect`
  does **not** break that promise, and the doc needs no edit: `CommandCollect.execute`
  returns `success=False` only when `discover_repos` found nothing
  (`src/tools/postup/commands/collect/collect.py:69-74`) or the output write failed
  (:99); a per-repo failure leaves `success=True` (:105). An implementor must not "fix"
  this by skipping `collect`. **One honest qualification:** the output-write failure at
  :99 *can* occur after repositories were discovered, so after this change there is a case
  where repos were found and `collect` still exits non-zero. The doc's sentence, read
  literally, does not cover it. That is the correct behaviour - a run that could not
  persist its contracts has not succeeded - so the doc sentence should gain
  "and its output was written" when someone next edits `postup.rst`. Not required by this
  rework, and listed here rather than silently left as a contradiction.
- **No `report_result` caller hides inside a command class.** `rg 'report_result' src/tools/`
  also matches `src/tools/klyreon/commands/assets.py:4` and
  `src/tools/postup/commands/enrich/enrich.py:14`, but both are docstring sentences
  describing that the CLI layer renders the result, not call sites. The conversion list
  above is therefore complete for `src/tools/`, and the "command classes never render or
  exit" invariant is intact.
- **`tui` and `serve` exit paths.** `postup tui` and `postup serve` return a
  `CommandResult` after a long-lived process ends; their `require_import` guard already
  panics before `report_result` when the extra is missing. Converting them affects only
  the post-exit failure report, not the running server.

## Test strategy outline

Per-tool `CliRunner` tests, matching the shape already established by
`tests/tools/dot/test_status_exit_code.py` and the 15 other cycle-1 exit-code files.

- **R2, the regression test that must fail first.** `invoke(cli, ["brief"])` with a mocked
  failing `CommandBrief` asserts `exit_code != 0`. Against the current code this fails
  (exit 0), which is the fail-first evidence the bug fix rule requires. The existing
  `TestBarePostupExitCode` cases stay; the new class is named for the subcommand so the
  two surfaces are no longer conflated.
- **R3, per command.** For each converted `dot` and `postup` subcommand: one case asserting
  `exit_code != 0` on a mocked failing `CommandResult`, one asserting `exit_code == 0` on a
  mocked successful one. Mock the command class, not the shell, as the cycle-1 files do.
- **`dot pull` plan error.** Mock `CommandPull.plan` to return a plan whose `error` is set
  and assert `exit_code != 0` and that the error text reaches the output. Also assert
  `cmd.execute` was never called, which pins "exit before any mutation".
- **Falsy-error and truthy-error guards.** Reuse the two cases cycle 1 added for bare
  `postup`: a failing result with `error=""` still exits non-zero, and a successful result
  carrying stale `error` text still exits 0. These bind the tests to `success`, not to the
  error string, so a future refactor that keys off `error` fails the suite.
- **No new `muc` test, and no change to the existing ones.** `tidy.py` is not edited, so
  there is no new behaviour to pin. `test_exits_nonzero_when_aggregate_result_fails`
  stays as the guard on the aggregate call's `exit_on_failure=True` wiring; it mocks a
  failure the real step helpers cannot produce, which is why R7 called it unreachable, and
  that observation stays deferred rather than acted on here.
- **Gate.** `uv run pytest tests/tools/dot/ tests/tools/postup/` for the narrow run, then
  the full suite. The suite's 10 pre-existing errors in
  `tests/tools/dot/test_pull_divergence_two_hosts.py` are environment-only (no gpg signing
  agent under the sandbox while `commit.gpgsign=true`) and are not this rework's concern;
  the new tests must not add to them, so they mock the command class rather than driving
  real git.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 5, question 1

Blockers, both fixed in the doc:

- **Test strategy omitted the stale exit-0 assertions the conversion breaks.** Verified
  against the repo: `tests/tools/dot/test_dot_commands.py:86-91` (`test_pull_failure`)
  mocks a failing `CommandPull` and asserts `exit_code == 0`, and the same shape recurs
  for `commit`, `unstage`, `push`, `rm`. Cycle 1 spent a separate commit (`cdc5c413`) on
  exactly this after the fact. `## Module placement` now carries an explicit
  existing-tests-to-change table and a mandatory `rg -n 'success=False' tests/tools/dot tests/tools/postup`
  sweep, so the assertion updates land in the same commit as the conversion.
- **`muc tidy` was recorded as a deliberate exit-0 case while its aggregate `success` is
  hardcoded `True`.** Accepted at first and fixed by deriving the aggregate from the step
  results - **then reverted, because the finding's premise is false.** Checking the step
  helpers showed that all six construct `success=True` and never set `success=False`
  (`merge_mac_metadata.py:120`, `lowercase_file_extensions.py:19`,
  `rename_equivalent_extensions.py:30`, `delete_by_extension.py:20`,
  `remove_empty_directories.py:19`, `dir_tree.py:100`); a recoverable failure is appended
  to `result.warnings` instead (`delete_by_extension.py:29`). Since `report_result` prints
  ` ✘ ` only on the `not result.success` branch, no step can ever print one, so `muc tidy`
  never prints a failure line and exits 0 and the PRD metric holds for it unchanged.
  `success=all(...)` would have been dead code - a constant `True` dressed as a
  computation - and exactly the unreachable-branch pattern R1 is deleting elsewhere this
  cycle. `tidy.py` is therefore untouched, R7 stays correctly deferred, and
  `## Interfaces & contracts` carries the evidence under "Not a finding: `muc tidy`".

Non-blockers and the question, all addressed rather than deferred, since each was a
one-line correction to the contract the implementor will copy:

- The prescribed CHANGELOG bullet named only one exception while the design listed two,
  and R5's survey output had no definite home. Fixed: the bullet names `muc tidy` and
  `bim doc triage --approve`, and `CHANGELOG.md` is stated as the durable home (not a
  completion report, which is not a tracked artifact).
- `bim doc triage --approve` (`src/tools/bim/doc_cli.py:298`) calls `_report_doc_result`
  with no `strict` argument and exposes no flag, so it is an **unconditional** exit-0
  surface, not a strict-gated one. Recorded separately, with a follow-up note.
- Internally inconsistent site counts. Fixed to one number used throughout. (The figure
  dispatch 1 was given, "17 conversions + 1 bypass rewrite + 1 aggregate-success fix", was
  itself wrong on both terms; dispatch 2 corrected the conversion count to 18 and the
  `muc` revert removed the aggregate fix. The live number is **18 conversions + 1 bypass
  rewrite = 19 edited sites**.)
- The `return` after the exiting `report_result` was justified by a false type-checker
  claim (`report_result` is `-> None`, not `NoReturn`). Re-justified as defence in depth,
  with an explicit note on why it is not the R1 duplicated-exit anti-pattern.
- `dot run` propagates failure as 1, never the wrapped command's own status. Recorded in
  `## Risks & edge cases` as accepted for this PRD, with the follow-up named.
- Question on where the `CommandResult` import lands in `dot/cli.py`, and an off-by-one
  `muc/cli.py` citation. Fixed: module scope beside the existing `buvis.pybase` imports at
  `dot/cli.py:8`, with the reason lazy-import does not apply, and the citation corrected to
  `muc/cli.py:91`.

dispatch 2 (codex): cardinal-sin 0, blocker 0, non-blocker 2, question 0

Both non-blockers were one-line factual corrections to the contract an implementor copies,
so both were fixed rather than only recorded:

- **Conversion totals were wrong.** `## Module placement` lists 13 dot + 5 postup = 18
  conversions, while the scope paragraph claimed 17 and 19. Corrected to one number used
  throughout: 18 conversions + 1 rewritten bypass branch = 19 edited sites (20 before the
  `muc` revert; the revert removed the twentieth).
- **The CHANGELOG bullet still overclaimed.** It named only `bim doc triage --approve` as
  an exception while the design also records `doc ingest` and `doc promote` as exit-0
  without `--strict`. The bullet is now scoped to failures rendered through
  `report_result`, which is the PRD's own metric, and names the whole `bim doc` family's
  behaviour.

dispatch 2 engagement re-run (codex): cardinal-sin 0, blocker 1, non-blocker 6, question 0

The first codex pass returned only 2 findings, which trips the minimum-engagement check,
so it was re-dispatched once with a prompt naming the six sections to inspect. This re-run
read the pre-revert doc, so its one blocker and one of its non-blockers concern the `muc`
change that no longer exists:

- **blocker, now moot:** the `muc` regression-test bullet both mocked `CommandTidy` and
  claimed to exercise its real `execute`, and asserted printed step output that
  `report_result` does not print on a failed result. Resolved by deleting that bullet with
  the rest of the `muc` change.
- **non-blocker, now moot:** `## Risks` described R7 as deferred while
  `## Interfaces & contracts` declared it closed. The revert makes "deferred" correct
  again.

Two findings were valid and are fixed:

- **The literal sweep could not establish coverage.** `rg 'success=False'` misses
  `CommandResult(False)`, spaced assignments, fixture-built failures and
  `MagicMock`-configured ones. The sweep is now three required steps: the literal search,
  an `rg -n 'exit_code'` audit of both trees, and adjudicating every failure the narrow
  gate exposes.
- **`test_pull_failure` would pass for the wrong reason.** It configures only
  `execute.return_value`, so its unconfigured `plan().error` is a truthy `MagicMock` and
  `dot/cli.py:pull` returns on the plan-error branch without ever calling `execute`
  (verified: only :99 configures `plan`). Flipping its assertion alone would still never
  test the `execute` failure. The design now specifies two tests: one with
  `RescuePlan()` asserting `execute` was called, and a separate plan-error test asserting
  it was not.

The re-run also confirmed three things with section-anchored evidence and no change
needed: `brief`'s `result.success`-guarded `console.print` means a failed brief skips the
text branch and reaches the exiting report; the `dot pull` wrapper preserves `plan.error`
as the failure line; and the retained `return` is sound as defence in depth.

Reviewer-verified, no change needed: every line number in R2, R3 and `## Module placement`
is real; the helper signature and semantics quoted in `## Interfaces & contracts` match
`console.py`; R2's fix does close R2; the other nine tools are fully converted; the
`dot pull` rewrite is correct and strictly safer; `dot materialize --hook` turning non-zero
cannot fail a git hook (`src/tools/dot/hostlinks/hooks.py:25-26` runs it with
`check=False` then `sys.exit(0)`) - now recorded in `## Risks & edge cases`; no cardinal
sin applies, since this is a behavioural change with no persisted state or schema and
reverting the diff restores the old status.

dispatch 3 (codex): cardinal-sin 0, blocker 0, non-blocker 8, question 0

Verification pass, run because dispatch 2's engagement re-run had raised a blocker. It
found no cardinal sin and no blocker, and confirmed four things with section-anchored
evidence:

- **`muc` needs no change.** "Every step succeeds, recoverable problems become warnings,
  and neither the step reports nor the successful aggregate enters the failure branch. No
  supplied path prints a failure line and exits zero." The revert was right, and `tidy.py`
  plus its tests stay unchanged.
- **The test prescriptions are correct**, including replacing the truthy `MagicMock` plan
  error with `RescuePlan()` and asserting `execute` was called, with the separate
  plan-error test asserting it was not.
- **R2 and R3 coverage is complete**: all 20 existing `report_result` calls are accounted
  for (13 dot conversions plus the already-converted `status`, 5 postup conversions plus
  the already-converted bare `postup`), and the `dot pull` bypass rewrite closes the one
  non-reporting path. No call site is missed.
- **The contracts are buildable**, including the module-scope `CommandResult` import, and
  the lazy command-class imports stay compatible.

Its four substantive non-blockers were all stale text left by the `muc` revert or wording
that overstated a claim, so all four were fixed rather than only recorded:

- The dispatch-1 log entry still carried the pre-revert count. It is now labelled as the
  historical figure it was, with the live number stated.
- `## Risks` placed `muc tidy`'s loop "in the two files under edit". Corrected: the loop is
  in `src/tools/muc/cli.py`, and neither edited file contains a loop.
- The CHANGELOG paragraph said the blanket claim "is true for every tool" after this
  rework. It is not, because `bim doc` reports through `_report_doc_result`. The paragraph
  now says the claim is **narrowed** to `report_result` failures, and the bullet says
  "reports its cleanup results in step order" rather than "as it runs", since
  `CommandTidy.execute` builds all four step results before the CLI renders any.
- `postup collect`'s quoted doc promise needed one qualification: the output-write failure
  at `collect.py:99` can fire after repositories were discovered, so there is a case where
  repos were found and `collect` now exits non-zero. Recorded, with the doc sentence that
  should gain "and its output was written" noted as a follow-up.
- Option 3's hypothetical guarantee was scoped to `report_result` callers, and its opt-out
  corrected to the single `muc tidy` loop.

result: ok
