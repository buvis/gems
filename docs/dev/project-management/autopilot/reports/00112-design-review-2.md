Transport: personal use-sonnet wrapper; requested sonnet, effort high; read-only, tools unused. Source codex role swapped to Anthropic.

Permission deny rule (/Users/bob/.claude/settings.json): Write(**/dev/local/**) is not matched by file permission checks — only Edit(path) rules are. Use Edit(**/dev/local/**) instead (Edit rules cover all file-editing tools).
No cardinal sins and no blockers. Findings and checked-correct notes follow. I used no tools and reviewed only the text you gave me.

## Findings

**1. non-blocker: Lossless bounded queue lets a stalled UI stall archives**
- Evidence: `## Interfaces & contracts` / Runner delivery. Workers do `put(event, timeout=0.2)` and retry until cancelled. "No event is silently dropped for an uncancelled successful instance."
- Impact: progress is advisory, but this ties archive wall-time to terminal and consumer health. It also needs the cancellation-aware retry loop and a 256-slot test matrix. If the consumer is stuck (blocked tty write, stopped ssh, slow `on_progress`), writers block inside `tar.add` callbacks after 256 events. That contradicts the PRD intent that "progress can never fail an archive".
- Suggested fix: use a latest-wins slot per label for `archiving` events. Keep `scanning` and `finalizing` as ordered boundary events, or pair a small bounded queue with drop-oldest-archiving. This removes the retry loop, the blocked-producer cancellation path and the backpressure tests. If you keep lossless, record why stalling the writer is accepted, since the design says "accepted" only implicitly.

**2. non-blocker: `on_tick` plus `refresh` may be avoidable, and it deviates from the PRD API**
- Evidence: the `Runner.__init__` signature adds `on_tick` beyond the PRD's `on_progress`-only API. The design admits this is a "refinement".
- Impact: the PRD requires only that the wait loop wakes at least every 0.2s. `Status.update` accepts any renderable. A small object whose `__rich__` computes elapsed time from the stored first-seen timestamps would be re-rendered by Rich's own refresh. That drops `on_tick`, `refresh()` and the tick-exception handling. The runner wake-up requirement stays either way.
- Suggested fix: either adopt the lazy-renderable approach, or add a sentence explaining why elapsed must be recomputed on the calling thread (for example, the lazy renderable would read `_LiveProgress` state from Rich's refresh thread).

**3. non-blocker: Unverified console and stream assumptions**
- Evidence: `### CLI rendering and lifecycle` says live mode keys on `sys.stdout.isatty()`, "even though introductory PRD wording mentions stderr/stdout". Final lines go through `_report_step` / `console`.
- Impact: nothing shows that `ConsoleAdapter.status` and the `console.success/failure` print path share one Rich `Console` bound to stdout. With two consoles, or a console bound to stderr, result lines print into a live region and garble it. With stderr redirected to a log while stdout is a tty, spinner control codes land in the log.
- Suggested fix: add a design line citing the Console instance and stream used by `status` and by the report methods. Add one test using a real Rich Console with `force_terminal=True` that prints a result line while the status is live.

**4. non-blocker: Status stop/restart on one object is tested only with mocks**
- Evidence: "stop it when the last active label finishes; restart the same object if later submitted work emits its first event". The live CLI tests assert `Status.update` and the factory call count.
- Impact: Rich `Status` wraps a `Live`, and restart behavior across Rich versions is not obvious. A mock cannot catch a broken restart in the real library.
- Suggested fix: add a smoke test with a real `Status` on a `Console(file=StringIO(), force_terminal=True)` covering start, stop and start again. Alternatively create a fresh status per active period and drop the restart claim.

**5. non-blocker: Elapsed time origin is the consumer's receipt time**
- Evidence: Risks section: "First-seen event receipt is the available elapsed-time origin; it excludes queue delay and waiting for a worker slot."
- Impact: if the consumer is blocked in a result-render or callback, the label's start time is later than the true start. The operator-visible elapsed time under-reports exactly when the UI is slow. Documented, but it is undercounting rather than noise.
- Suggested fix: acceptable for v1. Note it in `docs/source/tools/backup.rst`. If it matters, add a monotonic timestamp to the `scanning` event rather than a fifth field. Otherwise keep the four-field contract.

**6. question: Can a label repeat, or a fallback re-emit phases?**
- Evidence: `_LiveProgress` keys by `label`, with "Phase changes preserve the first timestamp". The system-tar fallback section says "preserve finalizing and the existing fallback note".
- Reading A: labels are unique per run, and finalizing fires once per instance. Reading B: duplicate labels can pass preflight, or a failed system attempt can emit a second `scanning`/`archiving` after an earlier `finalizing`.
- Impact: under B, `finish(label)` removes another instance's row, or the status shows a phase going backwards.
- Suggested fix: state that labels are unique (cite the duplicate-aware preflight). Define whether the fallback re-emits `archiving`. Add a test for the repeated-phase case.

**7. non-blocker: Cancellation race can yield a success with no final events**
- Evidence: "After cancellation, no new progress enqueue is required"; the enqueue callable returns without enqueueing once cancel is set.
- Impact: an instance that finishes publishing after cancel is set can yield a successful `StepResult` without its trailing `archiving`/`finalizing` events. The design says this is acceptable, but the sentence "No event is silently dropped for an uncancelled successful instance" never states that cancelled-run successes are exempt.
- Suggested fix: say explicitly that `finish(label)` on the result is the only guaranteed UI transition, and that tests must not assert event completeness for results yielded during cancellation.

**8. non-blocker: Timed completion wait versus PRD 00111 recovery logic**
- Evidence: "use `completed.get(timeout=0.2)`. Catch `queue.Empty` as a normal wake-up", alongside "Do not refactor ... lost-notification recovery".
- Impact: PRD 00111's lost-notification recovery may treat the blocking `get` as authoritative, or add a poll of futures on its own timeout. A new 0.2s `Empty` path could change that behavior, such as a double-scan or an earlier recovery trigger. The design asserts preservation without naming the current recovery trigger.
- Suggested fix: name the existing recovery condition and show that a 0.2s `Empty` neither triggers nor suppresses it. Keep the existing lost-notification test unchanged and passing.

## Checked correct

- **Rollback and data safety (`## Architecture fit`, `## Module placement`):** no persistence, config keys or schema are added. `tar_archive.py` keeps the existing temp/fsync/`os.replace` order and `BaseException` cleanup. Nothing here needs a rollback plan or migration.
- **Secrets and auth:** none are introduced.
- **Unbounded resources:** the progress queue is bounded at 256, the event rate is throttled at 0.2s per archive, and `_LiveProgress` state is bounded by the active labels. The design handles this (see finding 1 for the tradeoff).
- **Observability:** the feature is the observability; terminal results stay authoritative (`finalizing means the stream closed, not that publication succeeded`).
- **Calling-thread contract and ordering (`### Runner delivery and tick`):** enqueue happens inside the capability before the future completes, so draining before yielding a result gives finalizing-before-result per label.
- **Accounting (`### Capability and writer hooks`):** `lstat` before each add counts only regular files. Symlinks and directories count zero, and hardlinks count `st_size`, matching `walk.total_bytes`. Accounting state is local per call, which handles the shared `CAPABILITIES` singleton.
- **Exception policy:** `_emit_progress` swallows only `Exception`, so cancellation-class `BaseException` still propagates.
- **Final flush exemption from throttling:** a sensible, explicitly flagged refinement. It resolves the short-archive case without sleeps (matches the review-log non-blocker).
- **Markup safety:** passing `rich.text.Text` to `Status.update` prevents label or `[NN%]` bracket parsing as markup.
- **Terminal confinement:** Rich and tty logic stay in `cli.py` only, and `plan()` and dry-run paths pass no callbacks.
