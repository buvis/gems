# Design: sysup run observability

## Architecture fit

All changes stay inside `src/tools/sysup/` (tool-isolated, no `src/lib` changes, no new deps). The existing layering holds: `config.py` (Pydantic schema + merge/validate) -> `runner.py` (execution, yields `StepResult`) -> `cli.py` (renders via `console`, folds into `attention.py`). This PRD adds one new leaf module, `runlog.py`, that `runner.py` owns exclusively (CLI never touches a log file handle, matching the existing "CLI renders, runner executes" boundary). `attention.py` and `step_result.py` get an additive `warned` status slotted beneath `expiring` in `_RANK` — no schema version bump (stays version 1; the PRD accepts older-reader incompatibility as a known risk).

## Module placement

- **New file**: `src/tools/sysup/runlog.py` — log lifecycle (dir resolution, retention, exclusive creation, append, close).
- **New file**: `tests/tools/sysup/test_runlog.py`.
- **Edit**: `src/tools/sysup/config.py` — add `sudo: bool = False` to `SysupCommand`.
- **Edit**: `src/tools/sysup/default.yaml` — set `sudo: true` on the `brew` entry (the only entry whose steps invoke cask installs that need primed credentials); leave `apt`/`snap` alone (`sudo` is already their argv[0], which the predicate below also catches).
- **Edit**: `src/tools/sysup/capabilities/sudo.py` — `prime()` gains the contextual banner immediately before spawning `sudo -v`.
- **Edit**: `src/tools/sysup/step_result.py` — add `"warned"` to `Status`.
- **Edit**: `src/tools/sysup/attention.py` — admit `"warned"` into `_RANK` (below `expiring`) and `_valid_entry`.
- **Edit**: `src/tools/sysup/runner.py` — status contexts, exit-0 error scan, timeout handling, conditional prime predicate, log integration, one-final-result-per-steps-entry semantics.
- **Edit**: `src/tools/sysup/cli.py` — selected-plan-only prime call, warned rendering, final log-path line, controlled `FatalError` handling for log I/O.

## Interfaces & contracts

### `src/tools/sysup/runlog.py`

```python
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from buvis.pybase.result import FatalError

__all__ = ["RunLog", "append_step", "logs_dir", "open_run_log", "prune"]

_NAME_RE = re.compile(r"^\d{8}T\d{6}Z(-\d+)?\.log$")
_KEEP = 9  # files kept BEFORE this run's file is created (10 total after)


def logs_dir() -> Path:
    """``$XDG_STATE_HOME/sysup/logs``, falling back to ``~/.local/state/sysup/logs``."""
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "sysup" / "logs"


@dataclass
class RunLog:
    """An open, exclusively-created run-log file. Not reused across runs."""

    path: Path
    _handle: object  # TextIOWrapper; typed loosely to avoid importing io types at module scope


def prune(directory: Path, *, keep: int = _KEEP) -> None:
    """Delete oldest matching log files beyond ``keep``, oldest-first.

    Premise re-checked per file immediately before each deletion using
    ``os.lstat(path).st_mode`` and ``stat.S_ISREG(...)`` — **not**
    ``Path.is_file()``, which follows symlinks and would let a symlink named
    like a log (pointing anywhere, including outside ``directory``) pass the
    check and be deleted. ``lstat`` reports the link itself, so a symlink
    always fails ``S_ISREG`` and is skipped, never followed, matching the
    PRD's "only regular files" premise literally. The basename must also
    match ``_NAME_RE``. A mismatch (wrong type or wrong name) is reported
    (not raised) and skipped. Ordering: by ``st_mtime`` (from the same
    ``lstat`` call, so no second syscall), filename as tie-breaker. Missing
    ``directory`` is a no-op. A file that disappears between the initial
    listing and its scheduled deletion (``FileNotFoundError`` from
    ``os.unlink``) is treated as already-pruned, not an error — a concurrent
    second `sysup` invocation racing retention is a known non-blocking risk
    (see Risks & edge cases), not a correctness bug this function must
    prevent. Raises ``FatalError`` wrapping any OTHER ``OSError`` hit during
    listing or deletion, with the offending path in the message, after
    attempting no further deletions this call.
    """


def open_run_log(start: datetime, plan_names: list[str]) -> RunLog:
    """Create today's run-log file exclusively and write its header.

    Resolves ``logs_dir()``, creates it (``mkdir(parents=True, exist_ok=True)``),
    does NOT call :func:`prune` itself (the caller prunes first — see Data flow).
    Base name: ``start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".log"``.
    On a same-second collision (``FileExistsError`` from exclusive open),
    retries with ``-1``, ``-2``, ... suffixes before the extension, first
    available wins. Opens with ``os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)``
    then wraps in a text handle — never ``os.O_TRUNC``, so an unexpected
    existing non-matching file is never silently overwritten (it just forces
    the next suffix). Writes the header:

    ```
    sysup run <start ISO-8601 UTC, seconds precision>
    plan: <comma-joined plan_names, or "(empty)">
    ```

    followed by a blank line, then ``handle.flush()`` and ``os.fsync(handle.fileno())``
    (same durability pattern as ``pybase.filesystem.atomic_write_text``, applied
    here to an append-mode handle rather than a tempfile-then-replace), and
    returns the open ``RunLog``.
    Raises ``FatalError`` wrapping any ``OSError`` from directory creation or
    the exclusive-create retry loop, WITH THE ATTEMPTED PATH in the message
    (e.g. ``f"could not create run log {path}: {exc}"``) — satisfying the
    PRD's "identify any retained path as incomplete in the error diagnostic"
    even when no file exists yet. If the exclusive create itself succeeds but
    the header write or flush then fails, the just-opened file descriptor is
    closed (``os.close(fd)``, suppressing any secondary close error) BEFORE
    re-raising ``FatalError`` — so a header-write failure never leaves an
    open handle that nothing closes. The cleanup differs by WHERE the failure
    happens: if the text-handle wrap (``os.fdopen(fd, ...)``) itself raised,
    the raw ``fd`` still belongs to this function and is closed with
    ``os.close(fd)``; if wrapping succeeded and the header ``write``/``flush``
    on the WRAPPED handle then failed, that handle (not the raw ``fd``, which
    the wrapper now owns and which a second ``os.close`` could double-close
    or close a since-reused descriptor) is closed with the handle's own
    ``.close()`` instead. Both branches suppress any secondary close error,
    since the original write/flush error is what gets reported. The ``FatalError``
    message for a header/flush failure names the just-created (but now
    incomplete and closed) path, so the CLI's diagnostic can call it out as
    incomplete rather than silently leaving an empty/partial file behind
    unexplained.
    """


def append_step(
    log: RunLog,
    entry: str,
    descriptor: str,
    *,
    captured: bool,
    status: str,
    exit_code: int | None = None,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    timeout_s: float | None = None,
) -> None:
    """Append one completed step's section, then ``handle.flush()`` and
    ``os.fsync(handle.fileno())`` (same durability pattern as ``open_run_log``'s
    header write above).

    ``descriptor`` is the argv joined with spaces (captured/timeout sections)
    or the ``use:`` capability name / interactive argv string (not-captured
    sections). Section markers, exactly:

    - captured, no timeout: ``=== <entry>: <descriptor> (exit <exit_code>) ===``
      followed by ``stdout`` written verbatim (preserving its own internal
      newlines, no per-line transformation), then a single ``\n``, then
      ``stderr`` written verbatim the same way — neither stream gets its own
      sub-header; a trailing blank line after both.
    - timed out (``timed_out=True``): ``=== <entry>: <descriptor> (timed out after <timeout_s>s) ===``
      followed by whatever ``stdout``/``stderr`` partial text is available
      (empty string if none) — never invents an exit code.
    - not captured (``captured=False``, interactive steps and capability
      results): ``=== <entry>: <descriptor> (<status>, not captured) ===``
      with no stdout/stderr section.

    Raises ``FatalError`` wrapping any ``OSError`` from the write or flush,
    WITH ``log.path`` in the message (e.g. ``f"could not append to run log
    {log.path}: {exc}"``) — the path is always known here (``log`` is an
    already-open ``RunLog`` with a real path), so this is the simple case of
    the "identify the incomplete path" requirement. The runner's caller is
    responsible for stopping further update steps on this exception (see
    Risks & edge cases); ``append_step`` itself performs no retry and leaves
    previously flushed sections intact (the file is not truncated or
    reopened on error). It does NOT close ``log`` on failure — the caller's
    ``finally`` (Log ownership, below) still calls :func:`close` exactly
    once regardless of how the generator unwound, so closing here too would
    double-close the handle.
    """


def close(log: RunLog) -> None:
    """Close the underlying handle. Raises ``FatalError`` wrapping ``OSError``,
    with ``log.path`` in the message, same rationale as :func:`append_step`."""
```

`close` is not in the PRD's explicit `New symbols` list (only `logs_dir`, `open_run_log`, `append_step`, `prune`) but is required to release the OS handle; it is a trivial wrapper the runner calls in `finally`, consistent with "release log and sudo resources in finally". Flag this as a one-symbol addition beyond the PRD's named list — necessary, not optional (a log handle with no close leaks an fd for the process lifetime), not a scope expansion.

### `src/tools/sysup/config.py`

```python
class SysupCommand(BaseModel):
    ...
    sudo: bool = False
```

`default.yaml`: `brew: {..., sudo: true}`.

### `src/tools/sysup/capabilities/sudo.py`

`SudoPrime.prime()` gains, immediately before `subprocess.run([sudo_path, "-v"], ...)` becomes `subprocess.run([sudo_path, "-p", "sysup needs your password: ", "-v"], ...)`:

```python
from buvis.pybase.adapters import console
...
console.info(
    "sysup needs your password to cache sudo for this run's updates; "
    "press Ctrl-D to skip (later steps will prompt themselves)"
)
```
(Wording deliberately says "this run's updates", not "cask upgrades" — `_should_prime` also fires for `apt`/`snap` entries and any `sudo: true` entry, none of which are casks; a cask-specific banner would misdescribe those triggers.)

printed only after `sudo_path` resolves and only immediately before the `-v` spawn (never when sudo is missing). The argv becomes `[sudo_path, "-p", "sysup needs your password: ", "-v"]`. Never claim Ctrl-C skips (the banner text above says Ctrl-D only). `prime()`'s return contract (stop callback) and the missing/declined-sudo nonfatal paths are unchanged.

### `src/tools/sysup/runner.py`

`runner.py` gains one new top-of-file import this PRD needs: `import contextlib` (for `contextlib.nullcontext()` in `_run_steps` and `contextlib.suppress(Exception)` in the `finally` block below) — alongside the module's own `runlog` import (`from sysup import runlog`) and `from buvis.pybase.adapters import console`.

- **Conditional prime predicate** (new, replaces always-prime-when-configured):
  ```python
  def _should_prime(selected: list[tuple[str, SysupCommand]]) -> bool:
      def _needs_sudo(command: SysupCommand) -> bool:
          return command.sudo or any(argv and argv[0] == "sudo" for argv in (command.steps or ()))

      return sys.stdin.isatty() and any(_needs_sudo(command) for _, command in selected)
  ```
  PRD text: "any selected entry has sudo true or **any step's** first token equals sudo" — this checks every step's `argv[0]` in the entry, not only the first step (an entry like `steps: [[echo, starting], [sudo, apt, upgrade]]` must still prime). `Runner.run` calls `self._prime()` only when `_should_prime(selected)` is true (previously: whenever `self._cfg.prime` was non-empty and not dry-run). `prime: []` behavior (no capability configured) is preserved — `_should_prime` gates *whether* to invoke it, `self._cfg.prime` still gates *what* runs. `_should_prime` is called with the already `--only`/`--tag`-filtered `selected` list (never the full config), so an unselected entry's `sudo: true` never triggers priming.
- **Progress status**: wrap each captured spawn and the whole `_run_use` capability-iteration loop in `from buvis.pybase.adapters import console` / `console.status(f"{name}: {' '.join(argv)}")` (captured steps) or `console.status(f"{name}: {command.use}")` (use entries), entered around the existing `subprocess.run`/capability-iteration call and exited before the next step starts. Interactive steps are never wrapped (a spinner over inherited stdio would corrupt child TTY output). `console.status(...)` returns a Rich `Status` context manager that renders nothing on a non-TTY console (Rich detects `Console().is_terminal`), satisfying "non-TTY status renders no escape sequences" with no new code.
- **Exit-0 error scan** (new function):
  ```python
  _ERROR_RE = re.compile(r"^\s*error:", re.IGNORECASE)

  def _scan_errors(stdout: str, stderr: str) -> list[str]:
      lines = [ln for ln in (stdout + "\n" + stderr).splitlines() if _ERROR_RE.match(ln)]
      return lines
  ```
  Called from `_run_steps` immediately after each successful (`returncode == 0`, non-timeout) `_run_argv` call, using the stdout/stderr that call's `_ArgvOutcome` now carries (see below). Prints at most 5 matches via `console.failure` (diagnostic, not a `StepResult`) immediately, then if `len(lines) > 5` prints `f"+{len(lines) - 5} more, see log"` — before the loop proceeds to the next `argv`, i.e. mid-entry, before the next step spawns.
- **`_run_argv` return type changes** to carry the captured text onward, since both the exit-0 scan and the log's captured-section need it and `StepResult` must stay a pure per-step reporting type (Alternatives, option 3):
  ```python
  @dataclass(frozen=True)
  class _ArgvOutcome:
      """Internal to runner.py — never yielded, never crosses into cli.py."""
      result: StepResult
      stdout: str = ""
      stderr: str = ""
      exit_code: int | None = None
      timed_out: bool = False
      timeout_s: float | None = None

  def _run_argv(self: Runner, name: str, argv: list[str], command: SysupCommand) -> _ArgvOutcome:
      ...
  ```
  Every existing `_run_argv` return site (empty argv, missing binary, interactive, ordinary capture, nonzero exit) wraps its current `StepResult` as `_ArgvOutcome(result=<that StepResult>)` — stdout/stderr/exit_code default to `""`/`""`/`None` for all of those except the ordinary-capture success/failure branches, which now pass `stdout=result.stdout, stderr=result.stderr, exit_code=result.returncode` from the `subprocess.run` `CompletedProcess` already held locally as `result` (today's code computes `result` and discards `.stdout`/`.stderr`/`.returncode` beyond the `== 0` check; this design routes all three out instead of discarding them — no new subprocess call; note the local variable is `CompletedProcess`, distinct from the `StepResult` of the same conceptual name inside `_ArgvOutcome.result` — name it `proc` in the real implementation to avoid the collision). The new `except subprocess.TimeoutExpired as exc:` branch returns `_ArgvOutcome(result=StepResult(name, success=False, message=f"{name} timed out after {command.timeout}s", command=name), stdout=_as_text(exc.stdout), stderr=_as_text(exc.stderr), exit_code=None, timed_out=True, timeout_s=command.timeout)` — `exit_code=None` here is the "no exit code invented" marker `append_step`'s timeout branch reads to format `(timed out after Ns)` instead of `(exit None)`. `_as_text(x: bytes | str | None) -> str` is a small new helper (`"" if x is None else x if isinstance(x, str) else x.decode(errors="replace")`) needed because `TimeoutExpired.stdout`/`.stderr` are `bytes` when `text=True` was NOT yet applied at timeout time vs `str` once it was — `subprocess.run`'s own `text=True` kwarg already normalizes the ordinary-exit case, but `TimeoutExpired`'s cached partial buffers predate that normalization in some CPython versions, so the design does not assume either type. Interactive steps never populate stdout/stderr/exit_code (unchanged: `subprocess.run` without `capture_output` there; `append_step` is called with `captured=False` for these, so its not-captured branch never reads `exit_code` anyway).
- **`_run_steps` rewrite** — exact signature and control flow, since this is the PRD's highest-risk rewrite (touches abort semantics, log threading, and diagnostic timing together):
  ```python
  def _run_steps(self: Runner, name: str, command: SysupCommand) -> Iterator[StepResult]:
      steps = command.steps or ()
      if self._dry_run:
          rendered = "; ".join(" ".join(step) for step in steps)
          yield StepResult(name, success=True, message=f"would run: {rendered}", command=name)
          return

      failed_outcome: _ArgvOutcome | None = None
      error_lines_total = 0
      for argv in steps:
          status_cm = contextlib.nullcontext() if command.interactive else console.status(f"{name}: {' '.join(argv)}")
          with status_cm:
              outcome = self._run_argv(name, list(argv), command)
          if self._log is not None:
              really_captured = not command.interactive and (outcome.exit_code is not None or outcome.timed_out)
              runlog.append_step(
                  self._log, name, " ".join(argv),
                  captured=really_captured, status=outcome.result.status,
                  exit_code=outcome.exit_code, stdout=outcome.stdout, stderr=outcome.stderr,
                  timed_out=outcome.timed_out, timeout_s=outcome.timeout_s,
              )
          if not outcome.result.success:
              failed_outcome = outcome
              if not command.continue_on_error:
                  break
              continue
          lines = _scan_errors(outcome.stdout, outcome.stderr)
          if lines:
              for ln in lines[:5]:
                  console.failure(ln)
              if len(lines) > 5:
                  console.failure(f"+{len(lines) - 5} more, see log")
              error_lines_total += len(lines)

      if failed_outcome is not None:
          yield failed_outcome.result
      elif error_lines_total:
          yield StepResult(
              name, success=True, status="warned", command=name,
              message=f"{name}: {error_lines_total} error line(s), see log",
          )
      else:
          yield StepResult(name, success=True, command=name)
  ```
  Exactly one `StepResult` is yielded per call, in every branch, including `continue_on_error=True` (previously it yielded one per step — this is the behavior change `## Interfaces & contracts`'s "one final result per steps-based entry" names, and the acceptance test's `-k observability` suite pins it). `_run_entry`/`_run_use`/`_run_steps`'s `self` already has `self._log` (set in `run`, see Log ownership below); no parameter threading is needed beyond that instance attribute, so `_run_entry`'s own signature (`def _run_entry(self, name: str, command: SysupCommand) -> Iterator[StepResult]`) is unchanged — it already calls `_run_steps`/`_run_use` as methods on `self`.
- **Timeouts**: covered above in `_run_argv` / `_ArgvOutcome`. No traceback; ordinary nonzero-exit handling (the non-timeout branches) is untouched.
- **`_run_use` logging** — the PRD requires a not-captured marker per yielded capability `StepResult` too ("each capability result have `=== <entry>: (<use or argv> (<status>, not captured)) ===` markers"), which the Interfaces section above didn't spell out for this method. `_run_use`'s existing loop (`for step in capability.run(**command.with_): yield replace(step, command=name)`) gains one `append_step` call per yielded step, inserted AFTER the `replace` so the logged `status`/`command` match exactly what's yielded upward, and OUTSIDE the `try`'s `except Exception as exc:` capability-error branch — a capability raising mid-iteration still logs each `StepResult` already yielded before the exception, then logs one more not-captured entry for the synthetic failure `StepResult` the `except` branch constructs, exactly mirroring `_run_steps`'s one-call-per-yielded-result pattern. `except FatalError: raise` is unchanged and still propagates BEFORE any `append_step` call for that iteration — a `FatalError` from inside a capability (today's existing propagation contract, e.g. `nvim-mason` raising for "nvim not found") is never logged as a capability result and is never swallowed by the logging addition, since `append_step` is called only on the happy path per yielded `StepResult`, never in the `except` handlers' control flow for `FatalError` itself. The capability-iteration `console.status(f"{name}: {command.use}")` wrap (described above under "Progress status") stays around the whole `for step in capability.run(...)` loop, not per-yielded-step, matching "the whole capability iteration" in the PRD text — each yielded step calls `append_step` while still inside that one status context.
- **Log ownership.** `Runner.run` opens the log once at the start of an ordinary (non-dry-run) invocation — see Data flow — assigning `self._log: RunLog | None` and `self.log_path: Path | None` (new `Runner.__init__` attributes, both defaulting to `None` so a fresh `Runner()` used only for `check_items`, as `_recheck_item` does, never touches the log). The existing `finally` block (`run`, today's L80-82) is restructured so stopping the sudo refresher(s) can never prevent the log from closing, or vice versa:
  ```python
  finally:
      for stop in stops:
          with contextlib.suppress(BaseException):
              stop()
      if self._log is not None:
          runlog.close(self._log)
  ```
  `contextlib.suppress(BaseException)` — not `Exception` — is deliberate: a plain `except Exception`/`contextlib.suppress(Exception)` does NOT catch `KeyboardInterrupt` (it subclasses `BaseException` directly), so a Ctrl-C arriving while a refresher's `stop()` callback is mid-call would propagate out of the loop immediately and skip the `runlog.close` line entirely — defeating "close on every exit, including interrupts" for exactly the interrupt case the PRD calls out. Swallowing `BaseException` in a cleanup-best-effort loop is the one place that's correct: `stop()` is a daemon-thread `Event.set()` wrapper (today's `SudoPrime.prime`) that cannot raise anything worth propagating, and the surrounding `finally` already guarantees the ORIGINAL exception (if `run`'s body raised one) keeps propagating once this block finishes — this `suppress` only shields one `stop()` call from ending the loop early, not the generator from ending at all. `runlog.close`'s own `FatalError` is deliberately NOT suppressed — a failure to close the evidence file is exactly the kind of failure the PRD wants surfaced (exit 1, no traceback), whereas a refresher-stop failure is best-effort cleanup of a background thread that must never mask whatever exception is already propagating through `finally`. `cli.py` reads `runner.log_path` after the generator is exhausted (see the `cli.py` binding fix below) — there is no other channel back to the CLI without changing `StepResult`, and `StepResult` must not carry run-level log metadata (Alternatives, option 3).
- **List/dry-run/status/refresh create no log**: `list_plan` returns before `Runner(...).run(...)` is ever called (existing early return in `cli()`); `Runner.run`'s own `if not self._dry_run:` guard (existing code, L73) is the one place `open_run_log`/`prune` get called, so `dry_run=True` already skips it structurally; `sysup status` and `sysup refresh` never call `Runner.run` at all (`_recheck_item` calls `Runner(cfg).check_items(...)` directly, bypassing `run` entirely, as today).

### `src/tools/sysup/step_result.py`

```python
Status = Literal["ok", "failed", "expiring", "expired", "unknown", "warned"]
```

`__post_init__`'s `not success and status == "ok"` fallback is untouched — `warned` is always passed explicitly with `success=True` (per PRD: "A warned result has success true").

### `src/tools/sysup/attention.py`

```python
_RANK = {"warned": -1, "expiring": 0, "unknown": 1, "expired": 2, "failed": 3}
```
("below expiring" = numerically below `0`; `-1` is deliberate, not a reshuffle of the existing three values, so unrelated ordinals are untouched.) `_valid_entry`'s `entry["status"] in _RANK` check admits `"warned"` for free. `RED` (`step_result.py`) is unchanged — `warned` is never red, so `fold_results`/`exit_code` continue to treat a warned-only run as exit 0 (PRD: "exit 0 unless a red result exists"). `fold_results` needs no signature change: a `warned` `StepResult` already carries `status="warned"` and a truthy `message`, so it folds through the existing `bad = [r for r in results if ... r.status != "ok"]` filter and `max(bad, key=lambda r: _RANK[r.status])` exactly like `expiring` does today. A clean recheck (`status="ok"`) still clears the entry via the existing `if not bad: folded.pop(name, None)` branch.

### `src/tools/sysup/cli.py`

- `_report_step` gains a `status == "warned"` branch (checked before the existing `elif step.success` so warned doesn't fall into the plain success-checkmark path): `console.warning(step.message or f"{step.label} warned")`.
- **Bind the `Runner` instance to a name.** Today's `cli()` (L167) is `for step in Runner(cfg, dry_run=dry_run).run(plan):` — the instance is never kept, so `log_path` would be unreachable after the loop. Change to:
  ```python
  runner = Runner(cfg, dry_run=dry_run)
  for step in runner.run(plan):
      _report_step(step)
      results.append(step)
  ```
  then, after the existing `_print_summary`/`_notify`/`write_state` sequence, print `console.info(f"full log: {runner.log_path}")` when `runner.log_path` is not `None` (i.e. always for an ordinary run; never for `list_plan`/`dry_run`, per `Runner.__init__`'s default above).
- Log I/O failures propagate as `FatalError` from `runlog.py` through `Runner.run` (uncaught inside the generator — Python generators propagate exceptions to the consuming `for` loop) to the SAME `except FatalError as exc: console.panic(str(exc)); return` already wrapping the `for step in Runner(...).run(plan):` loop in `cli()`. No new exception handling needed there. This satisfies "raise through the runner to the CLI's controlled error handler: no traceback and exit 1" with the existing code path.
- "Omit the completed-run `full log:` line on failure": "failure" here means a `FatalError` (log I/O, or config load) — satisfied structurally, `console.panic` calls `sys.exit(1)` inside the `except FatalError` branch, so execution never reaches the `full log:` print below it. A run that completes normally but contains one or more failed `StepResult`s (ordinary red exit code 1, no `FatalError`) still reaches and prints the `full log:` line — the PRD's "even for clean runs" phrasing describes the minimum guarantee (don't suppress it on success), not a maximum; the log evidence is exactly what a failed run's operator needs to inspect, so suppressing the path on an ordinary failed exit would be the wrong behavior, not a stricter reading of the requirement.

## Data flow

1. `cli()` builds `plan` as today, then calls `Runner(cfg, dry_run=dry_run)`.
2. `Runner.run(selected)`:
   a. `check_items` (unchanged, still yields item `StepResult`s first — before log open, since item checks are not logged: Risks & edge cases below is silent on this, PRD's "Header records UTC start and plan names" names only `plan_names`, so the header is written once the plan is known, right before entry execution begins).
   b. If not dry-run: `runlog.prune(runlog.logs_dir())` then `self._log = runlog.open_run_log(start=<now, captured once>, plan_names=[name for name, _ in selected])`; `self.log_path = self._log.path`.
   c. `stops = self._prime()` only if `_should_prime(selected)` (gated as above).
   d. For each `(name, command)` in `selected`: `_run_entry` executes, threading `self._log` down to `_run_steps`/`_run_use`/`_run_argv` so each completed step (captured, timeout, or capability-yielded) calls `runlog.append_step` before the generator yields its `StepResult` upward — log write happens first so a crash mid-yield still has the evidence on disk.
   e. `finally`: stop sudo refresher(s), then `if self._log is not None: runlog.close(self._log)`.
3. `cli()` consumes the generator, calling `_report_step` + appending to `results` per yielded `StepResult` exactly as today.
4. After the loop: existing fold/notify/write_state sequence, then the new `full log:` line.
5. **Creation/pruning failure starts no update steps**: because `prune`+`open_run_log` run in step (b), BEFORE the `for name, command in selected` loop in step (d), a `FatalError` there propagates out of the generator before any command spawns — "zero update spawns after creation/pruning failure" falls out of the existing control flow with no extra guard needed.
6. **A later write failure starts no further update steps**: `append_step`'s `FatalError` is raised from inside the generator while yielding step N's section; because `for name, command in selected: yield from self._run_entry(...)` is a plain loop, an uncaught exception from within one entry's steps propagates immediately and the loop never reaches entry N+1 — again no extra guard, this is `continue_on_error`'s existing per-step early-return made stricter by exception propagation instead of a `return`.

## Reuse inventory

- `buvis.pybase.filesystem.atomic_write_text` / `atomic_write_bytes` (`src/lib/buvis/pybase/filesystem/atomic_write.py`) — **not used for the run log.** It replaces a file wholesale via `os.replace`; the log is append-per-step to one handle kept open for the run's duration, and must never overwrite an existing file (collision -> suffix, not replace). `runlog.py` therefore implements its own `os.O_CREAT | os.O_EXCL` open, consistent with the Invariant that durable state writes go through atomic machinery — this is append-only evidence, not a state file (the PRD says so explicitly), so the exclusivity-not-atomicity contract is intentional and distinct.
- `attention.state_path()`'s `$XDG_STATE_HOME` fallback pattern (`src/tools/sysup/attention.py:25-29`) — reused verbatim in `runlog.logs_dir()` (same env var, same `~/.local/state` fallback, just a different leaf dir `sysup/logs` vs `sysup/attention.json`'s parent `sysup/`).
- `buvis.pybase.adapters.console` (`ConsoleAdapter.status`, `.info`, `.warning`, `.failure`) — reused for progress, the sudo banner, and warned rendering; no new console method needed. Searches tried: `rg -n "status\(" src/lib/buvis/pybase/adapters/console/console.py` (found `status()`, confirms a Rich `Status` context manager already exists — no new progress-rendering code needed); `rg -n "def (info|warning|failure)" src/lib/buvis/pybase/adapters/console/console.py`.
- `sysup.step_result.StepResult`/`RED`/`Status` — extended in place (additive `Literal` member, additive `_RANK` entry), per the Reuse-over-new-type default; no new result type.
- Greps tried for an existing retention/pruning helper: `rg -n "unlink|glob.*log|retention" src/tools/sysup/ src/lib/buvis/pybase/filesystem/` — nothing found; `nvim.py`/`pip.py` capabilities have no file-retention logic to borrow. `prune` is new.
- Greps tried for an existing timeout-to-StepResult mapping: `rg -n "TimeoutExpired" src/tools/sysup/` — nothing found (timeouts currently propagate uncaught); new in `runner.py`.

## Alternatives considered

1. **Chosen: dedicated `runlog.py` module, one open handle threaded through `Runner`.** Smallest surface that satisfies "append-per-step" + "close on every exit" without changing `StepResult`'s shape.
2. **Smallest-diff alternative: buffer all step output in memory, write the whole log once at the end via `atomic_write_text`.** Rejected: the PRD requires "append and flush each completed step" specifically so a log-creation/append failure stops further updates *and* so evidence survives a crash mid-run (interrupt handling, `FatalError` paths) — a single end-of-run write loses everything on any mid-run failure, which is exactly the case the log exists to cover. The extra ~60 lines of `runlog.py` buy crash-surviving evidence; nothing else.
3. **Store log metadata on `StepResult` itself** (e.g. a `log_path` field) instead of a `Runner.log_path` attribute. Rejected: `StepResult` is a frozen per-step dataclass reused for item checks and capability results that have nothing to do with the run log; threading a run-level path through every instance duplicates it `len(results)` times and couples an orthogonal concept into the result type `attention.py` and tests already pattern-match on.

## Risks & edge cases

- **Likely next change 1**: a `--no-log` escape hatch if evidence volume becomes a concern in practice; this design's `Runner.run` boundary (log opened once, threaded as one optional object) already supports gating it off with `self._log = None` and `append_step` no-ops — no architecture change needed later.
- **Likely next change 2**: size-based (not count-based) retention. `prune`'s `keep` parameter and mtime-ordering make this a parameter change, not a rewrite, but the current design does nothing to cap single-file size (PRD accepts this: "no size cap").
- **Likely next change 3**: streaming output live instead of capture-then-print (explicitly out of scope this PRD). The progress-status approach (spinner only, no streamed bytes) deliberately does not block this — a later change swapping `subprocess.run(capture_output=True)` for `Popen` + incremental reads would replace `_run_argv`'s body without touching `runlog.py`'s per-step `append_step` contract.
- **Edge case**: `command.timeout is None` (no timeout configured) — `subprocess.run(..., timeout=None)` never raises `TimeoutExpired`, so the new `except` branch is simply never hit; no special-casing needed.
- **Edge case**: a capability's `.run()` generator itself raises mid-iteration after yielding some `StepResult`s (existing `test_capability_generator_error_is_caught_inside_iteration` behavior) — each already-yielded result still gets its own `append_step` call before the catch produces the final synthetic failure `StepResult`, which gets its own `append_step` too; no special handling, this falls out of "log each yielded step as it's yielded."
- **Edge case**: `_should_prime` must read `command.sudo` on the ALREADY-FILTERED `selected` list (post `--only`/`--tag`), not the full config — otherwise an unrelated unselected entry's `sudo: true` would prime credentials nobody asked for this run.
- **Accepted (not a design gap): unbounded log volume/size.** `subprocess.run(capture_output=True)` already buffers a step's full output in memory today (pre-existing behavior, unchanged by this PRD) and the log then persists it to disk. The PRD's own Risks section states this explicitly and accepts it: "Log volume: Ten files, no size cap; document location and full-output retention." This is a deliberate, recorded, PRD-level scope decision (a count cap, not a byte cap), not an unexamined "figure it out later" — Likely next change 2 above already names size-based retention as the follow-up if volume becomes a problem in practice. No code change is required by this finding; it is recorded here so a reviewer sees the rationale without re-litigating PRD scope at the design stage.
- **Accepted (not a design gap): no migration plan for the `warned` status / schema version 1.** The PRD's own Risks section states this explicitly and accepts it: "Older state readers: Older builds reject warned entries; retain version one as accepted in discovery." `_valid_entry` already rejects any `status` not in `_RANK`, so an OLDER sysup reading a NEWER state file with a `warned` entry degrades to "malformed state, treat as empty" (`read_state`'s existing `return {}` fallback) rather than crashing — a safe, already-existing failure mode, not a new one this PRD introduces. No migration is needed because nothing is removed or renamed — `warned` is a pure addition an older reader simply doesn't recognize. No code change required by this finding.

## Test strategy outline

- `test_runlog.py`: XDG/fallback dir resolution; header content and UTC format; a captured section round-trip with both streams present; a not-captured marker; a timeout section with partial bytes and partial text inputs; flush-per-step (assert file content visible before `close()`); a loop of 11 `(prune(dir), open_run_log(...))` call pairs retaining exactly 10 files on disk afterward — `open_run_log` itself never prunes (per its own contract above), so the retention assertion exercises `prune` directly, not `open_run_log` alone; two same-second `open_run_log` calls producing `-1` suffix; `prune` skipping a non-matching regular file and a symlink, reporting both, deleting neither; `close()` on an already-broken handle; `FatalError` raised (not a bare `OSError`) from a monkeypatched `os.open`/write/`os.fsync` failure in each of create/append/close/prune — `fsync` is exercised because `open_run_log`'s header write and `append_step` both flush via the same pattern atomic_write_text uses elsewhere in this codebase (`handle.flush()` then `os.fsync(handle.fileno())`), so a stubbed `os.fsync` failure is a real, specified failure mode, not a contract the design invented for the test; a failed create/prune leaves zero entries written to any new file (nothing to assert beyond "no file" + "no later calls happened", enforced by the runner-level test below).
- `test_runner.py` additions: `_should_prime` true/false matrix (TTY × sudo-flag × argv[0]-sudo × no-sudo); status-context entered/exited around a captured spawn (assert `console.status` called, mocked); one final `StepResult` for a multi-step entry under all three outcomes (clean / some warned / some failed, with and without `continue_on_error`); exit-0 `error:` line scan (case-insensitivity, 5-then-overflow line, mid-entry timing asserted via call-order on a mocked console); timeout -> failed `StepResult` with message and partial-output threading into a mocked `append_step`; log open/append/close call sequencing (mocked `runlog` module) including zero further `subprocess.run` calls after a mocked `open_run_log`/`append_step` raises `FatalError`; dry-run and `check_items`-only paths never call `runlog.open_run_log`.
- `test_sysup_cli.py` additions: warned rendering via `_report_step`; `full log:` line present after a clean/warned run and absent after `list_plan`/`dry_run`/a `FatalError`-raising run; a real non-terminal `rich.console.Console` instance asserted to emit no ANSI escapes around a status context.
- `test_config.py` / `test_default_config.py`: `sudo` field default `False`, `brew` entry's bundled default `True`, legacy configs without the field unaffected.
- `test_sudo.py`: banner printed once, after sudo resolves and before the primed `-v` spawn, using the new `-p` argv; declined/missing-sudo paths unchanged; banner text never mentions Ctrl-C.
- `test_attention.py`: `warned` round-trips through `fold_results`/`to_notify`/`exit_code`; ranks below `expiring`; a clean recheck clears a warned entry.
- `test_invariants.py`: include `runlog.py` in whatever existing sweep it runs (e.g. a `CommandResult`/console-only-output invariant check), per the module list in the PRD's Structural Decomposition.

All mocked; no real subprocesses, sudo, network, or wall-clock sleeps — matches the PRD's Success Metrics and the existing suite's patterns (`mocker.patch("sysup.runner.subprocess.run", ...)`, `mocker.patch("sysup.runner.shutil.which", ...)`).

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 3, non-blocker 0, question 1

All 3 blockers fixed: `_run_argv`'s return type now carries stdout/stderr/timeout info via a new internal `_ArgvOutcome`; `cli.py`'s `Runner(...)` call is now bound to a `runner` local before the loop so `runner.log_path` is readable afterward; `_run_entry`/`_run_steps`/`_run_argv` now have exact post-change signatures and pseudocode instead of prose. The 1 question (ambiguous stdout/stderr log formatting) is resolved: "verbatim, then one `\n`, then verbatim" replaces "each on their own lines".

dispatch 2 (codex): cardinal-sin 2, blocker 6, non-blocker 2, question 1

Codex's sandbox could not read the repo (`PreToolUse` denied its file reads), so it reviewed the pasted doc text only, calibrated as if this were a from-scratch production system rather than a 7-module tool-local observability PRD; both cardinal-sin findings and all 6 blockers are addressed below.

The 2 cardinal-sins ("unbounded output/log volume", "no migration/rollback for the `warned` status") are both PRD-level scope decisions already explicit and accepted in the PRD's own Risks section ("Log volume: Ten files, no size cap..."; "Older state readers: Older builds reject warned entries; retain version one as accepted in discovery") — not undocumented "figure it out later" gaps. Recorded with full rationale in `## Risks & edge cases` rather than re-litigated as new design decisions; no code change needed, since nothing about the design introduces a NEW unbounded or unmigrated surface beyond what the PRD already scoped and accepted.

All 6 blockers were real design gaps and are fixed: (1) `_run_steps`'s pseudocode now uses `contextlib.nullcontext()` for interactive steps instead of unconditionally wrapping every step in `console.status`; (2) `_should_prime` now checks every step's `argv[0]` in an entry, not only `steps[0][0]`, matching the PRD's "any step's first token" wording; (3) `_ArgvOutcome` gained an `exit_code` field populated from the real `CompletedProcess.returncode` and threaded into `append_step`, so captured sections report the actual exit code instead of a hardcoded `None`; (4) `prune`'s docstring now specifies `os.lstat` + `stat.S_ISREG` instead of `Path.is_file()`, which follows symlinks and would have let a matching symlink pass the "regular file" check; (5) `open_run_log`/`append_step`/`close` now each name the affected path in their `FatalError` message, and `open_run_log` explicitly closes its own just-opened fd before re-raising on a header-write/flush failure so no handle leaks even when no `RunLog` is ever returned; (6) `Runner.run`'s `finally` block now stops each sudo refresher under `contextlib.suppress(Exception)` so a refresher-stop failure can never prevent `runlog.close` from running (and vice versa — `close`'s own `FatalError` is deliberately left unsuppressed, since a failed log close is exactly the kind of failure this PRD wants surfaced).

The 2 non-blockers (concurrent-run retention races; sudo banner saying "cask upgrades" for non-cask triggers) are recorded, not fixed: concurrent `sysup` invocations are out of scope for this PRD (no existing lock/coordination primitive to reuse, and the PRD names no concurrency requirement) and are noted in `prune`'s docstring as a known non-blocking race; the banner wording is corrected to "this run's updates" since it was a one-line, zero-risk fix worth taking anyway. The 1 question (does a failed-but-not-fatal run still print `full log:`) is resolved in the `cli.py` section: yes — the PRD's "even for clean runs" is a minimum guarantee, not an exclusion of failed-but-otherwise-complete runs, and the log is exactly the evidence an operator needs after a failure.

dispatch 3 (codex, verification): cardinal-sin 0, blocker 2, non-blocker 3, question 1 (after re-verification; 8 of the 11 prior findings confirmed RESOLVED by this reviewer)

The 2 still-open blockers are fixed: (7) `contextlib.suppress(Exception)` in the `finally` block does not catch `KeyboardInterrupt`/`SystemExit` (both subclass `BaseException` directly), so an interrupt during a refresher's `stop()` could skip `runlog.close` entirely — changed to `contextlib.suppress(BaseException)`, which is safe specifically because `stop()` (a daemon-thread `Event.set()` wrapper) has nothing worth propagating and the surrounding `finally`/generator semantics still let the real exception (if any) continue past this block once it finishes; (12) `open_run_log`'s header-failure cleanup specified a raw `os.close(fd)` even after the fd had already been wrapped in a text handle via `os.fdopen`, which could double-close or close a reused descriptor — the docstring now distinguishes "wrap itself failed" (raw `os.close(fd)`) from "wrap succeeded, write/flush on the wrapped handle failed" (close the wrapped handle instead).

The 1 non-blocker confirmed STILL OPEN (concurrent retention) was already recorded as an accepted, not-fixed limitation in `## Risks & edge cases` — no new action needed, the reviewer is just confirming the earlier disposition held. Of the 3 genuinely NEW findings: the exit-code/captured-flag non-blocker is fixed (`_run_steps` now computes `captured` from whether a process actually spawned — `outcome.exit_code is not None or outcome.timed_out` — rather than merely `not command.interactive`, so an empty-argv/missing-binary outcome no longer falsely claims a captured `(exit None)` section); the capability-logging question is fixed by adding an explicit `_run_use` logging paragraph (a gap in the Interfaces section — `_run_use`'s per-yielded-step `append_step` call, placed after `replace()` and outside the `except Exception` capability-error branch so a mid-iteration `FatalError` still propagates unlogged-and-unswallowed, exactly as today); the test-outline non-blocker (retention test contradicted `open_run_log` never pruning) is fixed by rephrasing the retention test as an explicit `prune`-then-`open_run_log` pair, and the `fsync`-failure test is now grounded by adding `os.fsync` to both `open_run_log`'s header write and `append_step`'s flush (matching the `atomic_write_text` durability pattern already used elsewhere in this codebase), rather than leaving `fsync` an untested assumption.

No cardinal-sins or blockers remain open. Review complete; proceeding to planning.
