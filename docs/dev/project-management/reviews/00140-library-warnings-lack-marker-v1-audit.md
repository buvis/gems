# Decision Audit Log: 00140-library-warnings-lack-marker-v1

PRD: `00140-library-warnings-lack-marker-v1.md`
Started: 2026-11-14T04:02:02Z
Completed: 2026-11-14T04:02:02Z
Autonomous: 19  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: design: where/how to bridge configuration-package logging.warning calls to console.warning with the ⚠ marker

**Choice**: auto-fix

**Rationale**: chose a logging.Handler installed at buvis_options() decoration time (not inside wrapper(), which would miss the earlier update-check resolve() call); handler attached to buvis.pybase.configuration logger, propagate left at default True (not False) since no code calls logging.basicConfig() anywhere in repo and False would break 9 existing caplog tests that capture at root. 3 review dispatches (1 claude + 2 codex-outage-fallback-to-claude), 2 blockers found and fixed, 3 non-blockers deferred (undersold docstring scope; unlocked _seen set), 1 question deferred (test strategy needs re-derivation after install-site fix, already incorporated).

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R1 test does not pin the handler's dedupe and does not assert the marker (test_click_integration.py:1291)

**Choice**: swept to a tail-sweep fix task

**Rationale**: two-voice actionable medium; mechanical test fix

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R3 idempotence test never restores pre-existing bridge handlers (test_click_integration.py:1357)

**Choice**: swept to a tail-sweep fix task

**Rationale**: two-voice actionable medium; mechanical test fix

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R2 emit reimplements ConsoleAdapter.warning instead of calling console.warning

**Choice**: discarded

**Rationale**: deliberate documented design deviation (soft_wrap keeps long config paths on one marked line); adding soft_wrap to the shared adapter method would change wrapping for every caller - out of PRD scope

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R4 bridge bypasses the console adapter method using raw Rich output

**Choice**: discarded

**Rationale**: single-voice; duplicate of R2, whose design rationale applies

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R5 installer test removes pre-existing bridge handlers permanently

**Choice**: discarded

**Rationale**: single-voice; same defect swept as the two-voice row R3

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R6 either-or assertion in test_update_with_malformed_settings_exits_cleanly

**Choice**: discarded

**Rationale**: single-voice; pre-existing test untouched by this diff, outside PRD scope

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R7 test_update_with_malformed_settings_exits_cleanly hedges with or

**Choice**: discarded

**Rationale**: single-voice; pre-existing test untouched by this diff, outside PRD scope

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R8 emit has no try/except with self.handleError(record)

**Choice**: discarded

**Rationale**: single-voice

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R9 new handler and installer have no docstrings

**Choice**: discarded

**Rationale**: single-voice

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R10 test_click_integration.py grows past the 800-line limit

**Choice**: discarded

**Rationale**: single-voice; pre-existing breach the planned task extended, splitting is out of PRD scope

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R11 bridge logger keeps propagate=True so a root handler would double-print

**Choice**: discarded

**Rationale**: single-voice; propagate left untouched by design decision; latent - nothing under src/tools installs a root handler

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R12 dedupe state _seen is an unbounded unlocked set

**Choice**: discarded

**Rationale**: single-voice; negligible for a short-lived single-threaded CLI

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R13 bridge installed at decoration time rather than command run time

**Choice**: discarded

**Rationale**: single-voice; not a defect - every loader-using tool goes through buvis_options and the install is idempotent

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R14 test file exceeds the 800-line limit

**Choice**: discarded

**Rationale**: single-voice; pre-existing breach, out of PRD scope

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R15 test_click_integration.py exceeds 800-line limit (1361 lines)

**Choice**: discarded

**Rationale**: single-voice; pre-existing breach, out of PRD scope

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: cycle 1: R16 _ConsoleWarningHandler and _install_console_warning_bridge lack docstrings

**Choice**: discarded

**Rationale**: single-voice

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: test_retired_twin_warning_deduped_across_two_invocations does not pin the handler's dedupe and does not assert the marker. It only counts "Retired config file" occurrences. `_warn_retired_twin` is already `@cache`-memoized (loader.py:32), so the count stays 1 with `_seen` removed. If the bare lastResort line is captured, it also stays 1 on pre-change code. Fix: assert the count of marked lines (the `⚠.*?Retired config file` regex used in the first test) across both invocations. Bind the handler's own dedupe with a non-cached message (for example the unsafe-path or unknown-key warning) through the real logger.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T04:02:02Z

**Decision**: test_install_console_warning_bridge_is_idempotent removes pre-existing `_ConsoleWarningHandler`s (with their `_seen` state) and its `finally` removes the one it installed. It never restores the originals, so the bridge stays uninstalled for later tests in the session until another `@buvis_options` decoration runs. Restore the saved handlers in `finally`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close
