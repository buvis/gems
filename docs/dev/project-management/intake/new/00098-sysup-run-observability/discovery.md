# Discovery: sysup run observability (live progress, framed sudo, errors surfaced live, retained log)

## Classification
Depth: comprehensive | Date: 2026-10-17
Source: `idea.md` beside this file.

Rationale: clarity medium (what and why given, how open), scope medium (runner, sudo
capability, config, cli, attention, docs), codebase impact high (modifies the
runner's subprocess contract and the sudo prime every run shares), complexity high
(spinner vs tee, log retention, status semantics for exit-0 errors).

## Problem

sysup runs every non-interactive step through `subprocess.run(..., capture_output=True)`
(`src/tools/sysup/runner.py:190-200`) and prints one line only when the step ends, so a
multi-minute `brew upgrade` shows nothing and reads as a hang. The first thing a run does
after the expiry checks is `sudo -v` (`capabilities/sudo.py:43`) with the stock
`Password:` prompt: nothing says sysup asked, why, or whether the prompt was already
answered, and it runs even when nothing in the plan needs sudo. Captured output is shown
only for a failed step, as that step's stderr; stdout is discarded always, and `Error:`
lines inside an exit-0 step (brew per-formula failures) vanish. PRD 00092 added the
end-of-run summary, persisted attention state and ntfy as a postmortem; nothing makes the
run legible while it runs, and nothing keeps the full output to re-read afterwards.

## Requirements

### Must have
- **R1 Live progress**: every captured (non-interactive) step runs inside
  `console.status("<entry>: <argv joined>")`, resolving to today's `✔`/`✘` line.
  `use:` capability entries get the same status around their iteration. Interactive
  steps are never wrapped.
- **R2 Framed sudo prompt**: before `sudo -v`, one `console.info` line says sysup is
  caching sudo credentials so cask upgrades do not stall mid-run and that a declined
  prompt only means later steps prompt themselves. The prompt itself is branded through
  `sudo -p "sysup needs your password: "`. The banner must not claim Ctrl-C skips the
  prompt (it aborts the run).
- **R3 Prime only when needed**: `SysupCommand` gains `sudo: bool = False`; `default.yaml`
  sets it on `brew`. Priming runs only when the selected plan holds an entry with
  `sudo: true` or a `steps` argv whose first token is `sudo` (apt, snap), and stdin is a
  TTY. `--only helm` never prompts.
- **R4 Errors surfaced live**: a failing step reports at the moment it fails (as today).
  After any captured step, lines matching `^\s*error:` (case-insensitive) in its retained
  stdout+stderr print condensed under the step line, capped at 5 with `+N more, see log`.
- **R4b Amber status for exit-0 errors**: a step that exits 0 but produced such lines
  yields `StepResult(success=True, status="warned", message=...)`. `warned` joins
  `Status`, `_RANK` (lowest amber rank), `_valid_entry`, `_report_step` (prints via
  `console.warning`), the summary and ntfy as an amber entry: notified once, exit 0,
  cleared by a clean run.
- **R5 Unattended-safe**: no spinner control codes on a non-TTY (Rich `Status` is a
  transient `Live` and renders nothing there; a test pins it with
  `Console(force_terminal=False)`); the sudo prime is skipped when stdin is not a TTY;
  nothing waits for input.
- **R6 Summary preserved**: the 00092 summary, state file, ntfy push and exit code keep
  their contracts; this work adds the live surface and the `warned` status only.
- **R7 Full output retained**: every ordinary run writes
  `$XDG_STATE_HOME/sysup/logs/<UTC timestamp>.log` (fallback `~/.local/state`), one
  `=== <entry>: <argv> (exit N) ===` section per captured step holding its full
  stdout and stderr, appended and flushed per step. The newest 10 files are kept;
  older ones are removed at the start of each run. The summary ends with one
  `full log: <path>` line whenever a log was written. `--list`, `--dry-run` and
  `status` write no log.
- **R8 Timeout handled**: `_run_argv` catches `subprocess.TimeoutExpired` and yields a
  failed `StepResult` (`<entry> timed out after Ns`) instead of a traceback; partial
  output captured before the timeout goes to the log.

### Nice to have
- Spinner text shows the step index within the entry (`brew (2/3): brew upgrade`).
- `sysup status` prints the newest log path.

### Out of scope
- Streaming or tee of child output (decided: spinner only, Q1).
- Retaining raw output of `use:` capabilities (pip-outdated, helm-repo-update,
  nvim-mason, pipx-python); they keep capturing internally. Follow-up once the log
  format has settled.
- Changes to interactive steps (`npm-check`) or to the ntfy message body.
- The duplicate ntfy implementation in `~/.claude/hooks/notify.py` (accepted in 00092).

## Constraints
- Backwards-compatible config: `sudo:` is additive with a false default; existing
  `buvis-sysup.yaml` files validate unchanged (`extra="forbid"` stays).
- No new dependencies: Rich (already a pybase dependency via the console adapter) and
  stdlib only.
- The runner stays output-free except through the console adapter; no `print`.
- The run log is an append-per-step file, not a note or state file, so the
  `atomic_write` invariant does not apply; a crash loses at most the current step's
  section. Attention state keeps `atomic_write_text`.
- The library (`src/lib/buvis/pybase/`) is not touched; `ConsoleAdapter.status()`
  already exists.
- Floor is Python 3.11.

## Codebase Context
- **Relevant code**:
  - `src/tools/sysup/runner.py` — `Runner.run` (expiry checks, `_prime`, entries),
    `_run_steps`, `_run_argv` (capture, interactive branch, no timeout handling).
  - `src/tools/sysup/capabilities/sudo.py` — `SudoPrime.prime()` (`sudo -v`, 60 s
    refresher thread, stop callback).
  - `src/tools/sysup/config.py` — `SysupCommand` (frozen Pydantic, `interactive`,
    `timeout`, `continue_on_error`), `SysupConfig.prime`.
  - `src/tools/sysup/step_result.py` — `Status` literal, `RED`, `StepResult`.
  - `src/tools/sysup/attention.py` — `_RANK`, `_valid_entry`, `fold_results`,
    `to_notify`, `state_path` (XDG pattern to copy for the logs dir).
  - `src/tools/sysup/cli.py` — `_report_step`, `_print_summary`, the ordinary-path
    tail, `_is_tty()`.
  - `src/tools/sysup/default.yaml` — `brew` entry, `prime: [sudo-prime]`.
  - `src/lib/buvis/pybase/adapters/console/console.py:137-146` — `status()` returns a
    Rich `Status` with the arrow3 spinner.
- **Conventions**: pytest + pytest-mock, class-based tests, subprocess always mocked
  (`mocker.patch("sysup.runner.subprocess.run")`), `tests/tools/sysup/conftest.py`
  isolates `XDG_STATE_HOME` (the logs dir lands under it for free). Docs in
  `docs/source/tools/sysup.rst` list every `SysupCommand` key in a table
  (lines 53-83) and name `sudo-prime` at line 105. CHANGELOG entries prefixed
  `**sysup**:`. Invariant test `tests/tools/sysup/test_invariants.py` lists runner
  modules that must not print or exit; a new log module joins that list.
- **Integration points**:
  - `_run_argv`: wrap the captured branch in `console.status(...)`; catch
    `TimeoutExpired`; return captured stdout/stderr alongside the `StepResult`
    (a small private record or a second return value) so `_run_steps` can log it and
    scan for `Error:` lines; yield `warned` when the scan hits on exit 0.
  - `_run_use`: wrap the capability iteration in `console.status(f"{name}: {use}")`.
  - `_prime`: take the selected plan; compute "needs sudo"; skip when nothing needs it
    or `sys.stdin.isatty()` is false.
  - `SudoPrime.prime()`: banner via `console.info`, `-p` prompt string.
  - `SysupCommand.sudo`, `default.yaml` `brew.sudo: true`.
  - New `src/tools/sysup/runlog.py`: `logs_dir()`, `open_run_log()`, `append_step()`,
    `prune(keep=10)`.
  - `cli.py`: `_report_step` handles `warned`; print the live `Error:` lines; summary
    appends `full log: <path>`.
  - `step_result.py` / `attention.py`: `warned` in `Status`, `_RANK`, `_valid_entry`.
- **Similar implementations**: `attention.state_path()` (XDG resolution to copy),
  `nvim_mason.py:86-110` (the one place that already handles `TimeoutExpired`),
  klyreon `vault/state.py` (same XDG + atomic pattern 00092 copied).

## Approach
- **Chosen**: keep `subprocess.run(capture_output=True)`; wrap each captured step in
  the existing Rich status spinner; after the step, write its full output to a per-run
  log and scan it for `^error:` lines; print those lines live and mark the step
  `warned` when it exited 0; prime sudo only for a plan that needs it, behind a banner
  and a branded `-p` prompt.
- **Why**: smallest diff that satisfies R1 to R7; no Popen or reader threads; the
  one-line-per-step summary and the 00092 contracts survive; non-TTY behaviour comes
  from Rich; the retained log makes the `Error:` heuristic safe to tighten later.
- **Rejected alternatives**:
  - Tee (stream + capture): interleaves child output with step lines, needs a Popen
    reader per pipe and TTY-aware fallbacks; informative but twice the code (Q1).
  - Spinner showing the child's last output line: same Popen rewrite as tee for a
    one-line gain (Q1).
  - Print all stderr after each step: brew `Warning:` chatter every run (Q2).
  - Flip exit-0-with-errors to `failed`: a heuristic false positive turns the run red
    and pushes ntfy every run (Q3).
  - Log only on not-ok runs or a single overwritten file: loses the evidence the
    heuristic is meant to be checked against (Q4).
  - Drop sudo priming: cask prompts land minutes in, under an animating spinner (Q5).
  - Migrate the four capabilities to a shared logging run helper now: doubles the
    surface; follow-up (Q6).

## Success Criteria
- A captured step enters `console.status` with `"<entry>: <argv>"` and an interactive
  step never does (status mocked on `sysup.runner.console`).
- A mocked step with exit 0 and `Error: firefox: ...` on stderr yields status `warned`,
  prints that line under the step, folds into `attention.json` as an amber entry, is
  pushed once, and exits 0; the next clean run clears it.
- A mocked exit-1 step still yields `failed` and exit 1 (00092 tests unchanged).
- After a run, `XDG_STATE_HOME/sysup/logs/` holds one file with a section per captured
  step containing the mocked stdout and stderr; after 11 runs it holds 10 files; the
  summary output ends with `full log: <that path>`; `--dry-run`, `--list` and `status`
  create no file.
- `sysup --only helm` never spawns `sudo`; `sysup --only brew` spawns
  `sudo -p "sysup needs your password: " -v` after one banner line; with stdin not a
  TTY no `sudo` is spawned; a `steps: [[sudo, apt, update]]` entry primes without a
  `sudo:` flag.
- A step raising `TimeoutExpired` yields a failed `StepResult` with `timed out` in the
  message and no traceback.
- `uv run pytest -m sysup -q`, `uv run mypy src/tools/sysup`, `uv run ruff check
  src/tools/sysup tests/tools/sysup` pass; `docs/source/tools/sysup.rst` documents
  `sudo:`, the `warned` status, the logs dir and retention; CHANGELOG has Added and
  Changed entries.

## Risks
- **Spinner over a mid-run sudo prompt**: if the prime is declined or a non-brew step
  needs sudo, the child prompts on `/dev/tty` under the spinner. Mitigation: R3 primes
  for every flagged entry; document `sudo: true` for custom entries that may prompt.
- **`Error:` heuristic noise or misses**: brew prints `Error:` for non-fatal
  situations too; pip uses `ERROR:`, uv `error:`, mise `mise ERROR`. Mitigation:
  case-insensitive `^\s*error:` only, amber not red, the full log retained; widen per
  evidence in a follow-up.
- **Rich Live and interleaved prints**: `_report_step` prints while a status may still
  be active for a multi-result capability. Mitigation: Rich routes prints above the
  live display; the capability status covers the whole iteration and the test asserts
  order of lines.
- **State schema widening**: `_valid_entry` rejects unknown statuses, so a state file
  written by the new build and read by an old one is dropped as malformed (returns
  `{}`). Accepted: same direction as 00096 adding its statuses; version stays 1.
- **Log growth**: a verbose `brew upgrade` can be megabytes. Mitigation: 10 files,
  pruned every run; no size cap in v1.
- **Thread-safety of the refresher**: unchanged from today; the stop callback still
  runs in the runner's `finally`.

## Open Questions
- Should the `Error:` scan also match mise's `mise ERROR ...` prefix in v1, or stay
  strictly `^\s*error:` until a log shows a missed case?
- Should the ntfy body for a `warned` entry carry the first `Error:` line (it does
  under the current `details[0]` rule) or a count? Default: unchanged rule.
- Does the banner print from `SudoPrime.prime()` through `console.info` (shortest),
  or should the runner yield an informational `StepResult` the CLI renders, keeping
  capabilities output-free? Default: `console.info` inside `prime()`; the invariant
  test covers the runner, not capabilities.
- Log filename timestamp: `%Y%m%dT%H%M%SZ` (sorts lexically, no colons for macOS
  Finder). Default unless create-prd prefers ISO with colons.

## Discovery Log

### Inferred from code (not asked)

- **Non-TTY degradation (R5)**: `ConsoleAdapter.status()` returns a Rich `Status`, a
  transient `Live`; Rich renders nothing for it when the console is not a terminal.
  Plain step lines print as today. No extra code for R5 beyond skipping the sudo prime
  when stdin is not a TTY (sudo cannot prompt there anyway).
- **Interactive steps**: `interactive: true` steps (npm-check) inherit the TTY; the
  spinner must not wrap them. Decision: no status context around interactive steps;
  they already show their own output.
- **"Ctrl-C to skip" the sudo prompt is not possible**: SIGINT goes to the whole
  foreground process group, so Ctrl-C during `sudo -v` raises KeyboardInterrupt in
  sysup and aborts the run. The decline path is config (`prime: []` in
  `buvis-sysup.local.yaml`) and the conditional prime (R3). The banner must not promise
  Ctrl-C skips.
- **Pre-existing bug found**: `Runner._run_argv` passes `timeout=command.timeout` but
  never catches `subprocess.TimeoutExpired`, so a timed-out step escapes as a traceback
  (only `nvim_mason.py:105` handles it). Carried as must-have R8.
- **Success criteria and priority**: not asked; the idea states the observable
  outcomes (brew visibly active, prompt attributable, errors visible during the run)
  and they map onto the criteria above. Priority left to backlog review.

### Q1: Live progress for captured steps (R1): which mechanism?
**Answer**: Spinner, keep capture. Wrap each captured step in `console.status(...)`;
no Popen rewrite, no streaming. Rejected: spinner + last output line (needs a reader
thread), tee (interleaves, loses the one-line summary during the run).

### Q2: Errors surfaced live (R4): what prints after an exit-0 step whose output holds errors?
**Answer**: Lines starting with `Error:` (match `^Error:` on the retained
stdout+stderr), printed condensed under the step line, capped. Rejected: all stderr
lines (brew `Warning:` chatter every run), exit code only (defers R4).

### Q3: Status of an exit-0 step that had `Error:` lines (summary, state, ntfy, exit code)?
**Answer**: New amber status `warned`: listed in the summary, persisted like
`expiring` (notified once, exit 0, cleared on a clean run). Touches `Status`, `_RANK`,
`_valid_entry`, docs. Rejected: flip to `failed` (a heuristic false positive turns the
run red), live print only (an unattended run loses it).

### Q4: Retained full output (R7): where does it live and how long?
**Answer**: Per-run file, always written, keep the newest 10:
`$XDG_STATE_HOME/sysup/logs/<UTC timestamp>.log`, one `=== <step> ===` section per
captured step; prune on each run. The summary prints one `full log: <path>` line.
Rejected: write only on not-ok (a missed error leaves no evidence), single overwritten
file (yesterday's evidence gone).

### Q5: Prime sudo only when needed (R3): how does sysup know a selected command needs sudo?
**Answer**: New `sudo: bool` on `SysupCommand` (default false), set on `brew` in
`default.yaml`; any selected step with `argv[0] == "sudo"` (apt, snap) also counts.
Prime runs only when the plan holds one such entry and stdin is a TTY. Rejected: argv
scan only (brew never primes, casks prompt under the spinner), drop priming (a cask
prompt lands minutes in with no framing).

### Q6: How far does R7 reach into `use:` capabilities that capture output themselves?
**Answer**: `steps:` entries only (brew, uv, mise, apt, snap get spinner + log +
`Error:` scan). `use:` entries get the spinner around their iteration and keep
returning `StepResult`s as today; retaining their raw output is an explicit follow-up.
Rejected: a shared run helper migrating the four capabilities now (doubles the surface
and test churn).

### Q7: One PRD or two (sudo work split out as a fast-track card)?
**Answer**: One PRD. The sudo part is about 30 lines; a split adds a PRD's worth of
ceremony. Sized like 00092.

### Q8: Anything else out of scope?
**Answer**: No; the list (tee/streaming, capability log retention, ntfy hook drift,
interactive steps unchanged) is complete. A `sysup logs` subcommand was offered as an
extra exclusion and not taken; it is simply not requested.
