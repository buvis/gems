# sysup: make an unattended run observable — progress, prompt context, visible errors

Status: processed, specced as PRD 00098. Recorded 2026-10-16.

## Problem

sysup runs its steps as a silent, long-lived foreground process and gives the
operator almost nothing to go on while it works. A real run on macOS surfaced
three distinct UX failures in one sitting (2026-10-16):

- **Silent in-progress steps.** Non-interactive steps run through
  `subprocess.run(..., capture_output=True)` (`runner.py` `_run_argv`), so a
  single `StepResult` line prints only after the whole command finishes. `brew`
  (order 10) runs `brew update; brew upgrade; brew cleanup`; a full formula and
  cask upgrade (firefox, chrome, docker-desktop, calibre, python@3.15, ...)
  takes minutes with zero terminal output. The run looks dead when it is
  working. The user read it as a hang and asked why "sysup outputs nothing".

- **A bare sudo prompt with no context.** The first thing a run does after the
  plan resolves is `sudo-prime` (`capabilities/sudo.py` `prime()` -> `sudo -v`).
  macOS shows the stock `Password:` prompt with no indication that *sysup*
  asked, why it needs sudo (cache the ticket so brew casks don't block
  mid-run), or that it is optional (a declined prompt is not fatal — later
  steps just prompt as before). sudo's non-echo input compounds it: with no
  echoed characters and no sysup framing, the user cannot tell whether they
  already typed the password, whether this is a fresh prompt, or whether the
  prompt is even sysup's.

- **Errors are hidden until the end — or forever.** Captured stdout/stderr is
  only surfaced for a *failed* step, and even then as a trailing block the user
  must scroll back to find. For an unattended maintenance run, "read the logs
  afterwards" is not an acceptable contract: the operator cannot be expected to
  comb output after the fact to discover that, say, several brew formulae were
  skipped because of a tap-trust warning. Mid-run errors inside an otherwise
  "successful" step (brew's per-formula `Error:` lines while the command still
  exits 0) are swallowed entirely.

Context: PRD 00092 added an end-of-run attention summary + ntfy for
expiries and failed steps. That helps the "missed a warning while scrolling"
case but does not address live progress, prompt framing, or in-step errors
that don't flip the step's success flag. The installed `sysup` on this host is
still the pre-00092 0.14.1 build, which has none of it.

## Idea (from the user)

Three things, logged together because they are one theme — an unattended run
must be legible while it runs, not only in a postmortem:

1. Show an **in-progress animation (or equivalent live signal)** for unattended
   steps, so a long silent step is visibly working rather than hung.
2. **Explain the sudo prompt** before it appears, and make it obvious it is
   sysup asking — don't drop the operator into a bare non-echo `Password:` with
   no idea whether they've already answered it.
3. **Surface errors as they happen**, in the terminal, during the run. The
   operator should not have to examine logs after sysup finishes to learn
   something went wrong.

## Discussion / design seeds (not yet decided)

### 1. Live progress for unattended steps

- A `console.status(...)` spinner already exists in the pybase `ConsoleAdapter`
  (`status()` -> Rich `Status`, arrow3 spinner). Wrapping each captured step in
  a status context would give "⠸ brew: upgrading…" that resolves to the final
  `✔`/`✘` line. Cheapest option; keeps output capture.
- Alternative: stream the child's output live (drop `capture_output`, inherit or
  tee the pipe) so the operator sees real brew/mise progress. Richer, but then
  the clean one-line-per-step summary is gone and output interleaves. The newer
  source already has an `interactive: true` path that inherits the terminal —
  this could become a third "stream but still capture for the summary" mode
  (tee), or `brew` could simply be marked interactive.
- Open: spinner vs live stream vs tee. Spinner is the smallest step and
  composes with the existing summary; tee is the most informative but needs
  care around TTY detection and non-TTY/unattended runs (cron, ntfy-only).

### 2. Prompt framing and the sudo prime

- Print a one-line banner before priming: what is about to be asked, why, and
  that declining is safe — e.g. `sysup: caching sudo credentials so cask
  upgrades don't block mid-run (press Ctrl-C to skip; steps will prompt as
  needed)`.
- Consider using `sudo -p` with a sysup-branded prompt string so the system
  prompt itself reads `sysup needs your password:` instead of bare `Password:`.
- Only prime when the resolved plan actually contains a step that needs sudo
  (today `prime: [sudo-prime]` runs unconditionally, even for `--only helm`).
  Skipping the prompt entirely when nothing needs it is the best fix for "why
  am I being asked for a password just like that".
- Non-echo confusion: a sysup banner immediately above the prompt is the
  practical remedy; the operator at least knows a prompt is live and whose it
  is. (System sudo won't echo; that's not sysup's to change.)

### 3. Visible errors during the run

- Decide what counts as an error worth surfacing live:
  - a step that exits non-zero (already captured, shown at end — pull it
    forward to the moment it fails);
  - stderr/`Error:` lines from a step that still exits 0 (brew's per-formula
    failures) — currently invisible.
- Options: tee stderr to the terminal as it streams; or scan captured output
  for error markers and echo a condensed warning immediately after the step,
  in addition to the end summary.
- Keep the end-of-run attention summary (00092) as the durable backstop, but
  the live surface is what this idea adds: the operator learns about a failure
  when it happens, not when they go digging.
- Full output is kept regardless of how it is surfaced. The condensed live and
  summary lines are extracted *views* over the retained log; the extraction
  that decides which lines are "relevant" will be refined over time, so it must
  always be able to re-read the complete captured output rather than a lossy
  pre-filtered copy. Capturing is therefore not in tension with live surfacing
  — we capture *and* stream/extract, never one instead of the other.

## Requirements (draft)

1. **R1 Live progress**: every unattended (non-interactive) step shows a live
   in-progress indicator while it runs, resolving to the existing success/
   failure line. A silent multi-minute step (brew upgrade) is visibly active.
2. **R2 Framed sudo prompt**: before any sudo prompt, sysup prints what it is
   asking for, why, and that declining is non-fatal. The prompt is attributable
   to sysup (branded prompt string and/or preceding banner).
3. **R3 Prime only when needed**: sudo priming runs only when the resolved plan
   contains a step that uses sudo; otherwise no prompt appears at all.
4. **R4 Errors surfaced live**: a failing step reports at the moment it fails,
   not only in the trailing summary. In-step errors that do not flip the step's
   exit code (e.g. brew per-formula `Error:` lines) are surfaced too. Surfacing
   extracts the *relevant* lines from the retained full output (R7); it never
   replaces or discards that output.
5. **R5 Unattended-safe**: the live indicators degrade cleanly when there is no
   TTY (cron / piped / ntfy-only), falling back to plain lines without spinner
   control codes, and never block waiting for input.
6. **R6 Summary preserved**: the 00092 end-of-run attention summary, state and
   ntfy notification remain the durable backstop; this work adds the live
   surface, it does not replace the postmortem.
7. **R7 Full output retained**: the complete captured stdout/stderr of every
   step is kept, not thrown away once a condensed line is shown. The live
   surface (R1, R4) and summary (R6) are *views* derived from this retained
   output; the extraction heuristics that pick "relevant" error lines will
   evolve, so the raw log must remain available to re-classify against and to
   fall back on when extraction misses. Decide where it lives (per-run log file
   under `$XDG_STATE_HOME/sysup/`, in-memory for the run plus on-failure
   persistence, or similar), retention/rotation, and how the summary points the
   operator at the full log for a given step.

## Open questions

- Progress mechanism: Rich `status()` spinner (keep capture) vs live stream vs
  tee (stream + capture for the summary)? Does `brew` just become
  `interactive: true`, or is a new per-step `stream`/`tee` mode cleaner so the
  summary still works?
- Should R3 (prime only when needed) extend to a general "does any selected
  step need sudo" probe, given Linux steps use inline `sudo apt ...` rather
  than the prime capability?
- For R4, is scanning the retained output for `Error:`/`Warning:` markers
  reliable enough, or should sysup only ever surface the process exit code and
  the live stream, and leave text classification alone? Either way the full log
  (R7) stays, so the extraction heuristic can be tightened later without having
  discarded the evidence.
- For R7, where does the retained log live and for how long: a per-run file
  under `$XDG_STATE_HOME/sysup/logs/`, kept only on failure or always, with
  what rotation? And how does the summary reference it (path + step name, or an
  offset into one combined run log)?
- How does live progress interact with the `interactive: true` steps that
  already own the terminal (npm-check)? Spinner must not fight an interactive
  child for the TTY.
- Does this fold into the PRD 00092 attention work as a follow-on, or is it a
  standalone "run observability" PRD?
