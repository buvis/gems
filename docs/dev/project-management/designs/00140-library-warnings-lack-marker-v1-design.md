# Design: Config library warnings print as bare log lines without the ⚠ marker

## Architecture fit

`src/lib/buvis/pybase/configuration/` already owns one Click-coupling exception
to the "library stays interface-agnostic" invariant: `click_integration.py`
imports `click` and, on a `ConfigurationError`, imports `buvis.pybase.adapters.console`
lazily inside the `_create_buvis_options` wrapper to render the failure
(`click_integration.py:370-374`). That wrapper runs once per CLI invocation,
inside the CLI process, after Click has parsed options and before the command
body runs. It is the correct and only place to install a process-wide bridge
from the configuration package's stdlib `logging` loggers to `console.warning`:
installing it anywhere inside `loader.py` or `resolver.py` (the warning sites)
would make those modules import the console adapter at their own import time,
which is the invariant this PRD's Success Metrics line explicitly protects.
`loader.py` and `resolver.py` keep emitting through `logging` exactly as
today; only the wrapper's bridge changes.

## Module placement

- Edit `src/lib/buvis/pybase/configuration/click_integration.py`:
  - add `_ConsoleWarningHandler` (new `logging.Handler` subclass) and
    `_install_console_warning_bridge()` (new module-level function).
  - call `_install_console_warning_bridge()` once inside `buvis_options()`
    (line 438), immediately beside the existing `_install_parse_args_patch()`
    call, **not** inside `wrapper()`. `buvis_options()` runs at command
    *decoration* time (when a CLI module applies the `@buvis_options`
    decorator, i.e. before any invocation), which is strictly earlier than
    `patched_command_parse_args`/`patched_group_parse_args`
    (`click_integration.py:229-245`) - the patch those install runs
    `_run_update_check_once` (`click_integration.py:173-210`) **before**
    Click calls `wrapper()`, and `_run_update_check_once` calls
    `ConfigResolver().resolve(...)` itself. Installing the bridge inside
    `wrapper()` would leave that earlier `resolve()` call unbridged: the
    `_warn_retired_twin` warning this PRD exists to fix is `@cache`-memoized
    (`loader.py:33`), so it would fire exactly once, unmarked, during that
    earlier resolve - before the bridge instance in `wrapper()` existed - and
    the PRD's own pinned CliRunner scenario would never see a marked line.
    Installing it at decoration time instead means the bridge exists before
    the parse_args patch can run at all, so every `resolve()` call in the
    process - the update-check's and the wrapper's own - is bridged.
- No change to `src/lib/buvis/pybase/configuration/loader.py` or `resolver.py`
  (both keep `logger.warning(...)`, unchanged API, per the PRD's Structural
  Decomposition).
- `CHANGELOG.md`: one `Fixed` entry.

No new files.

## Interfaces & contracts

```python
# src/lib/buvis/pybase/configuration/click_integration.py

class _ConsoleWarningHandler(logging.Handler):
    """Renders WARNING+ records from the configuration loggers via console.warning.

    One instance lives for the process once installed; `_seen` dedupes
    identical messages across repeated resolve() calls in the same process
    (e.g. a tool that resolves config in a loop).
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self._seen: set[str] = set()

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if message in self._seen:
            return
        self._seen.add(message)
        from buvis.pybase.adapters import console
        from rich.markup import escape

        console.warning(escape(message))


def _install_console_warning_bridge() -> None:
    """Idempotently attach `_ConsoleWarningHandler` to the configuration logger tree.

    Target logger: `logging.getLogger("buvis.pybase.configuration")` - the
    shared parent of `loader.py`'s and `resolver.py`'s module loggers
    (`buvis.pybase.configuration.loader`, `buvis.pybase.configuration.resolver`),
    both created via `logging.getLogger(__name__)` and propagating to it by
    default. Deliberately does **not** touch `propagate` (stays the default
    `True`): `rg -n "basicConfig" src/ tests/` confirms no code anywhere in
    this repo attaches a handler to the root logger, so today a
    `logger.warning(...)` from `loader.py`/`resolver.py` propagates all the
    way to the root and, finding zero handlers in the whole chain, trips
    stdlib `logging`'s `lastResort` fallback - a bare `WARNING:<logger>:<msg>`
    line straight to stderr, which *is* the bug this PRD reports. Once
    `_ConsoleWarningHandler` is attached at the `buvis.pybase.configuration`
    level, `logging`'s handler walk finds a handler there, so `lastResort`
    never fires - the fix does not need `propagate = False` to stop the bare
    line; it stops because a real handler now exists. Setting
    `propagate = False` was tried and rejected: `pytest`'s `caplog` fixture
    attaches its capture handler to the **root** logger by default, so
    `propagate = False` here silently breaks every existing test using the
    bare `caplog.at_level(logging.WARNING)` / `caplog.text` / `caplog.records`
    form against these loggers the moment any `@buvis_options`-decorated
    module is imported anywhere in the same process (decoration time, not
    invocation time - see `## Module placement`) - which a full pytest run
    across this monorepo's many CLI tools essentially guarantees. Confirmed
    against the real suite: `tests/lib/pybase/configuration/test_loader.py:751,778`,
    `test_loader_directive_merge.py:193,202,211`, and
    `test_tool_config_keys.py:65,74,85` all rely on exactly that unscoped
    default and would stop seeing these WARNING records. Leaving `propagate`
    at its default costs nothing today (no root handler exists to
    double-print against) and keeps every existing `caplog` call site
    working unchanged; the double-print risk the PRD's Risks section names
    is real only if some future code calls `logging.basicConfig()` (or
    otherwise attaches a root handler) - tracked as a non-blocking risk
    below, not solved speculatively now. Also deliberately does **not** call
    `config_logger.setLevel(...)`: the logger's default level is `NOTSET`, so
    its *effective* level is inherited from the root logger (`WARNING` by
    default in stdlib `logging`) and WARNING records already pass through
    unchanged; explicitly setting `WARNING` here would instead pin the
    subtree's effective level regardless of what the root logger's level is
    later set to (e.g. a future `--debug` wiring that lowers the root to
    `DEBUG` to surface `loader.py`/`resolver.py`'s existing `logger.debug`
    calls), silently reintroducing the suppression this design must avoid.
    The handler's own `level=logging.WARNING` (set in `__init__`) is the only
    filter needed - it already drops DEBUG/INFO records at the handler, which
    is where this design's console-marker concern lives.
    """
    config_logger = logging.getLogger("buvis.pybase.configuration")
    if any(isinstance(h, _ConsoleWarningHandler) for h in config_logger.handlers):
        return
    config_logger.addHandler(_ConsoleWarningHandler())
```

Call site (inside `buvis_options()`, `click_integration.py`, line 438, beside
the existing `_install_parse_args_patch()` call - decoration time, before any
invocation and before the parse_args patch can run):

```python
    _install_parse_args_patch()
    _install_console_warning_bridge()

    if callable(settings_class_or_func) and not isinstance(settings_class_or_func, type):
        ...
```

No other signature in the package changes. `get_settings`, `buvis_options`,
`ConfigResolver.resolve`, and every `logger.warning(...)` call site in
`loader.py` (`_warn_retired_twin`, the two "Skipping unsafe config path"
sites) and `resolver.py` (`_warn_unknown_shared_keys`) are untouched.

## Data flow

1. A CLI module applies `@buvis_options(...)` to a command, which runs
   `_install_console_warning_bridge()` (alongside `_install_parse_args_patch()`)
   at decoration time - before any invocation, and before the parse_args
   patch that later triggers an early `resolve()` call. No-op after the first
   decorated command in this process (`_ConsoleWarningHandler` already
   attached).
2. The CLI command is invoked. Click's patched `parse_args` may run
   `_run_update_check_once` (`click_integration.py:173-210`), which calls
   `ConfigResolver().resolve(...)` before `wrapper()` runs - already bridged
   per step 1.
3. `wrapper()` itself also calls `resolver.resolve(...)`, which internally calls
   `ConfigurationLoader` methods that may call `logger.warning(...)`
   (`buvis.pybase.configuration.loader`) and may itself call
   `_warn_unknown_shared_keys` (`buvis.pybase.configuration.resolver`).
4. Each `logger.warning(...)` call creates a `LogRecord` and routes it to the
   `buvis.pybase.configuration` logger's attached `_ConsoleWarningHandler`
   (module loggers propagate to their parent by default).
5. `_ConsoleWarningHandler.emit` dedupes by exact message text within the
   process and calls `console.warning(escape(message))`, which prints
   ` ⚠ <message>` through the same Rich console every other CLI warning uses.
6. `propagate` stays at its default (`True`), so the record still continues
   up to the root logger exactly as before this change - existing
   `caplog`-based tests (which capture at root by default) are unaffected.
   The record is never double-printed today because nothing in this repo
   attaches a handler to the root logger (`rg -n "basicConfig" src/ tests/`
   found none); `lastResort` - the stdlib fallback that produced the bare,
   unmarked line this PRD reports - no longer fires because
   `_ConsoleWarningHandler` is now a real handler found during the walk. If a
   future change ever does attach a root handler, that handler would now
   also render the same record (a double-print) - see Risks below.

## Reuse inventory

- `src/lib/buvis/pybase/adapters/console/console.py:90` - `ConsoleAdapter.warning(message)`:
  the exact ` ⚠ <message>` renderer this design calls. Reused as-is.
- `src/lib/buvis/pybase/adapters/console/console.py:383` - the `console` singleton,
  already imported lazily elsewhere in this same file
  (`click_integration.py:370`, the `ConfigurationError` branch). Reused as the
  import pattern for the new handler's `emit`.
- `src/lib/buvis/pybase/adapters/console/console.py:386-423` -
  `logging_to_console()` (a context manager that attaches a `CapturingRichHandler`
  to the **root** logger for the duration of a `with` block) and
  `src/lib/buvis/pybase/adapters/console/capturing_rich_handler.py:10` -
  `CapturingRichHandler(RichHandler)`. Both considered and **not reused**: this
  PRD needs a handler scoped to the `buvis.pybase.configuration` subtree only
  (not root, so it cannot swallow or double-render unrelated application
  logging), installed once for the process rather than per-`with`-block, and
  rendering through `console.warning`'s ` ⚠ ` marker specifically rather than
  `RichHandler`'s level-prefixed line - none of which `logging_to_console`
  provides. `rg -n "logging_to_console" src/` confirms it is currently unused
  by any CLI, so this is not a regression of an existing caller.
- `src/lib/buvis/pybase/adapters/console/capturing_rich_handler.py:10-26` -
  `CapturingRichHandler.emit` is the structural precedent for a small
  `logging.Handler` subclass that renders through the console adapter
  (confirms the pattern; code itself not reused, different target method).
- Greps tried beyond the above (nothing else found): `rg -n "dedup|_seen"
  src/lib/ src/tools/` (no reusable single-process dedupe-by-message helper);
  `rg -n "class.*Handler" src/lib/` (only `CapturingRichHandler`); `rg -n
  "propagate" src/lib/` (no existing logger-propagation handling to reuse or
  collide with).

## Alternatives considered

1. **Smallest-diff option: patch each `logger.warning` call site to call
   `console.warning` directly** instead of `logging.warning`. Rejected: it
   pulls `buvis.pybase.adapters.console` into `loader.py`'s and `resolver.py`'s
   import graph (an import-time UI-framework import, exactly what the
   library-stays-interface-agnostic invariant forbids - Success Metric 2 of
   the PRD names this directly), and a TUI/API/WebUI process that imports
   `ConfigurationLoader`/`ConfigResolver` without Click would now pull in
   `rich` at import time too.
2. **Chosen: a logging handler on the configuration logger tree, installed
   once from the CLI wrapper** (PRD's "agoge option (a)", this design). Keeps
   `loader.py`/`resolver.py` on plain `logging`, isolates the console
   dependency to `click_integration.py` (already the file with the one
   sanctioned Click/console exception), and the bridge activates for every
   `@buvis_options`-decorated command without each command's own code
   changing.
3. **A dedicated `logging.Filter` + root-level `CapturingRichHandler` reuse**
   (install `logging_to_console()`'s handler at CLI startup instead of a new
   class). Rejected: `CapturingRichHandler` renders the stdlib level name via
   `RichHandler`'s own formatting, not `console.warning`'s ` ⚠ ` marker and
   `STYLE_WARNING_MSG` styling the PRD's Success Metrics line requires
   verbatim; reusing it would mean rewriting `RichHandler.render()` output to
   match ` ⚠ <message>` exactly, which is more code than the ~20-line handler
   this design adds, for a worse fit.

The chosen design is the smallest change that keeps the library
interface-agnostic; it is one logging handler and one call site larger than
option 1, which is the cost of honoring the invariant.

## Risks & edge cases

- **Double-print under a future root logging config** (the PRD's own Risks
  line): today this is inert - `rg -n "basicConfig" src/ tests/` finds no
  root handler anywhere in the repo, `--debug` only sets `settings.debug`
  (`click_integration.py:435`) and configures nothing in `logging` itself, so
  there is nothing for the new handler to double-print against. `propagate`
  is deliberately left at its default `True` (see `## Interfaces & contracts`
  for why `propagate = False` was tried and rejected: it silently breaks 9
  existing `caplog`-based tests that capture at root by default). The
  residual risk is real only if a *future* change calls
  `logging.basicConfig()` or otherwise attaches a handler to the root logger
  - at that point the same record would render twice (once via
  `_ConsoleWarningHandler`, once via the new root handler). Non-blocking:
  flagged for whoever adds that future root handler to scope it (e.g.
  `logging.getLogger("buvis.pybase.configuration").propagate = False` at that
  later call site, where the tradeoff against `caplog` can be weighed against
  that change's own test suite) rather than solved speculatively here.
- **`caplog`-based tests that assert on configuration warnings**: unaffected
  by this change. `propagate` is untouched, so every existing test using the
  unscoped `caplog.at_level(logging.WARNING)` / `caplog.text` / `caplog.records`
  form (`tests/lib/pybase/configuration/test_loader.py:751,778`,
  `test_loader_directive_merge.py:193,202,211`,
  `test_tool_config_keys.py:65,74,85`) keeps receiving these records at root
  exactly as before. The new tests this PRD adds (Test strategy below) must
  not call any `@buvis_options`-decorated CLI entrypoint in the *same test
  process* as a bare caplog-at-root assertion without accounting for the new
  `_ConsoleWarningHandler`'s own console output alongside it - both now fire
  for the same record, which is by design (console marker for users,
  unchanged logging capture for tests), not a conflict.
- **Next likely changes**: (1) another library subpackage (e.g. a future
  `src/lib/buvis/pybase/filesystem` warning) wanting the same bridge -
  `_install_console_warning_bridge` is deliberately scoped to the
  `buvis.pybase.configuration` logger name only, so extending it means adding
  a second installer/logger-name pair, not widening this one, which keeps
  each bridge's dedupe set scoped to one subsystem's warnings; (2) a
  per-message-template (not per-exact-message) dedupe, if a future warning
  interpolates a changing value a caller wants deduped by template - the
  exact-message dedupe chosen here is correct for today's three sites (two
  are already per-path/per-key messages that should each print once by
  design, not once per template).
- **Process-lifetime handler state**: `_seen` lives as long as the handler
  (the process). A long-running process that calls `resolve()` many times
  with the *same* bad config will warn once total, by design (the PRD says
  "once per process"); a test must call `_ConsoleWarningHandler()` fresh (or
  reset `config_logger.handlers`) between cases that need the same message to
  warn again, rather than relying on `_install_console_warning_bridge()`'s
  idempotency across test invocations of the same process.

## Test strategy outline

- CliRunner test (the PRD's pinned scenario): with a retired `*.local.yaml`
  twin present, invoke a `@buvis_options`-decorated command once; assert the
  captured output contains exactly one ` ⚠ Retired config file ...` line
  (`console`'s styled output, not a raw `logging` line).
- Same fixture, invoke the command twice in one test (two `CliRunner.invoke`
  calls in the same process): assert the warning still prints only once
  total, proving the dedupe.
- `--debug` CliRunner test: same retired-twin fixture, pass `--debug`; assert
  still exactly one ` ⚠ ` line - the risk this PRD's Risks section calls out,
  verified inert today since `--debug` attaches no root handler.
- Existing `caplog` regression check: run the existing suite's
  `test_loader.py`, `test_loader_directive_merge.py`, and
  `test_tool_config_keys.py` caplog assertions unchanged, in the same pytest
  session as the new CliRunner tests above (not in isolation), to prove the
  bridge's process-wide decoration-time install does not silently break them.
- Direct unit test on `_ConsoleWarningHandler`: construct one, call `.emit()`
  with two records carrying the same `getMessage()` text, assert
  `console.warning` (monkeypatched/spied) is called once.
- Unit test on `_install_console_warning_bridge`: call it twice, assert
  `logging.getLogger("buvis.pybase.configuration").handlers` gains exactly one
  `_ConsoleWarningHandler` instance, and assert `.propagate is True`
  (untouched default) so a later edit does not reintroduce the rejected
  `propagate = False`.
- Regression guard for the invariant: a static check (or existing import-time
  test, if one exists) that importing `buvis.pybase.configuration.loader` and
  `buvis.pybase.configuration.resolver` standalone (no `click_integration`
  import) still imports no `rich`/`click` - confirms the console dependency
  stayed confined to `click_integration.py`.

## Review log

Question (open, not fixed): the Test strategy section's CliRunner scenarios should be re-verified by the implementor against the corrected install site (decoration-time, in `buvis_options()`), since they were drafted before the fix.

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 1, question 1

Non-blocker (open, not fixed): `_install_console_warning_bridge`'s docstring undersells its scope — it covers the whole `buvis.pybase.configuration` subtree (including `click_integration.py`'s own logger), not just `loader.py`/`resolver.py`. Harmless today; flagged for a future doc pass.

Non-blocker (open, not fixed): `_ConsoleWarningHandler._seen` is a plain unlocked `set`, a latent thread-safety gap if a server-style call path (e.g. `bim serve`) ever calls `resolve()` concurrently. Low priority — all current call sites are CLI-startup, single-threaded.

dispatch 2: codex unavailable, Claude fallback (sandbox denied all file/shell access in the codex run - empty findings)
dispatch 2 (claude-fallback): cardinal-sin 0, blocker 1, non-blocker 2, question 0

dispatch 3: codex unavailable, Claude fallback (sandbox denied all file/shell access in the codex run - empty findings)
dispatch 3 (claude-fallback): cardinal-sin 0, blocker 0, non-blocker 0, question 0
