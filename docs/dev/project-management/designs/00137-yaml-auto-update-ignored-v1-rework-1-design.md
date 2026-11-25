# Rework design: 00137-yaml-auto-update-ignored-v1, cycle 1

Source review: docs/dev/project-management/reviews/00137-yaml-auto-update-ignored-v1-review-1.md (head_sha 28a0580dc7c736e9654bf5a2b1abcdaaa8abc490)

## Architecture fit

Prior fix: none - there was no prior rework fix. Cycle 1's build pass (commits `e2cb1c59`, `d7fbeccc`, `b03f713f`, range `8d98134f..28a0580d`, `git diff --stat` = 12 files, 193 insertions) changed `_run_update_check_once` from `(ctx)` to `(ctx, args)` and made it resolve settings itself from raw argv via a new `_extract_config_path` helper, instead of moving the check into the `buvis_options` wrapper after `ConfigResolver.resolve` as the PRD asks. The cycle-1 CRITICAL was **introduced by that build pass**, not merely exposed by it: `tests/tools/sysup/conftest.py:20` has patched `_run_update_check_once` with a one-parameter `lambda _ctx: None` since commit `221bce63`, well before this PRD, and the patched `parse_args` calls the stub with two arguments outside `contextlib.suppress`, so every sysup/dot CLI test raises `TypeError: <lambda>() takes 1 positional argument but 2 were given` (measured at head `28a0580d`: `86 failed, 1711 passed, 10 skipped, 1 xfailed, 10 errors`, 76 `TypeError` occurrences).

A second regression from the same build pass surfaced at this design gate and is reproduced here: the old code called `check_and_update(GlobalSettings())` (`git show 8d98134f:…click_integration.py:142`), so the documented global opt-out `BUVIS_AUTO_UPDATE=false` was always read. The new code resolves `_resolve_settings_class(ctx)` instead, which for any tool with its own `env_prefix` (`src/tools/dot/settings.py:9` = `BUVIS_DOT_`) no longer reads `BUVIS_AUTO_UPDATE` at all, so `auto_update` falls back to its default `True` and the check runs. Measured: `pytest "tests/tools/dot/test_filter_cli.py::TestFilterIsolation"` -> 2 failed, both `AssertionError: uv was executed`, with `BUVIS_AUTO_UPDATE=false` in the subprocess env (`tests/tools/dot/test_filter_cli.py:96`). That is PRD Success Metric 2 ("`BUVIS_AUTO_UPDATE=false` keeps working") broken by the fix meant to honour the setting, and it is the real cause of the `tests/tools/dot` redness - `tests/tools/dot` has no `_run_update_check_once` stub at all (`rg -n _run_update_check_once tests/` returns exactly one hit, the sysup conftest).

The work lands entirely in the shared library's Click integration layer (`src/lib/buvis/pybase/configuration/`), which every tool's CLI depends on, plus the test suites that stub it. No tool package changes.

## Module placement

- `src/lib/buvis/pybase/configuration/click_integration.py` - edit. `_run_update_check_once` keeps its two-parameter signature (no revert); the `--config-dir` gap is closed by a sibling extractor; the broad `contextlib.suppress(Exception)` is narrowed.
- `tests/tools/sysup/conftest.py` - edit. The stub's arity follows the production signature.
- `tests/tools/sysup/test_cli_update_hook.py` - **new file**. The stub-arity guard from Interfaces §1 (it must live beside the sysup autouse fixture to exercise it).
- `tests/lib/pybase/configuration/test_click_integration_auto_update.py` - **new file**. The `--config-dir`, default-discovery and arity-contract tests go here rather than growing the already-1250-line `test_click_integration.py`.
- `docs/source/configuration.rst` - edit. The landed line at `:830-833` overclaims ("the fully resolved settings (CLI > ENV > YAML > defaults)"); the early check reads no CLI overrides. Replacement sentence, verbatim: "The update check honours ``auto_update`` from the configuration file selected by ``--config`` or ``--config-dir``, or found by default discovery. A tool-prefixed ``BUVIS_<TOOL>_AUTO_UPDATE`` overrides it; the global ``BUVIS_AUTO_UPDATE`` applies only when no tool-prefixed variable is set. Command-line overrides are not applied to this check."
- `CHANGELOG.md` - no change. The `Fixed` entry landed in cycle 1 (`CHANGELOG.md:28`, in the `8d98134f..28a0580d` diff), so the changelog rule is already satisfied for this PRD.

## Interfaces & contracts

**1. The stub-arity fix (the CRITICAL).** Closes: `R4 🔴 _run_update_check_once now takes (ctx, args), but tests/tools/sysup/conftest.py:20 still monkeypatches it with lambda _ctx: None`.

`src/lib/buvis/pybase/configuration/click_integration.py` keeps exactly:

```python
def _run_update_check_once(ctx: click.Context, args: list[str]) -> None:
```

`tests/tools/sysup/conftest.py:20` becomes exactly:

```python
monkeypatch.setattr("buvis.pybase.configuration.click_integration._run_update_check_once", lambda _ctx, _args: None)
```

`rg -n _run_update_check_once tests/` returns exactly one stub site today, so
this is the only edit needed; any future stub must take `(_ctx, _args)`.

**The guard must bind to the stub, not to the production signature.** A test
that only inspects `signature(click_integration._run_update_check_once)` passes
both before and after the fix (the production function already has `(ctx, args)`
at head `28a0580d`, and `tests/lib/...` never loads the sysup autouse fixture),
so it would not have caught this CRITICAL. The guard is instead a sysup CLI
smoke test that exercises the patched `parse_args` path with the autouse stub
fixture active, in `tests/tools/sysup/test_cli_update_hook.py`:

```python
def test_sysup_cli_runs_with_the_update_check_stub_installed(runner) -> None:
    """The autouse stub must satisfy the real hook's call signature."""
    from sysup.cli import cli

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert not isinstance(result.exception, TypeError)
```

This fails with `TypeError: <lambda>() takes 1 positional argument but 2 were
given` against the current stub and passes once the stub is fixed, which is the
fail-first evidence `rules/testing.md` requires.

**2. `--config-dir` honoured by the early resolution.** Closes: `R1 🟠 [4/4] --config-dir is not honoured by the new early resolution` (and, with it, `R10 🟡` on repeated-option precedence).

Replace `_extract_config_path` with one extractor that serves both options and matches Click's last-wins precedence:

```python
def _extract_option_value(args: list[str], option: str) -> str | None:
    """Return the LAST value of ``option`` in raw argv, or None.

    Honors both ``--opt VALUE`` and ``--opt=VALUE``, and the ``--``
    end-of-options sentinel (arguments after it are positional).
    Last-wins, matching Click's own handling of a repeated option.
    """
```

`_run_update_check_once` then resolves with both:

```python
config_path = _extract_option_value(args, "--config")
config_dir = _extract_option_value(args, "--config-dir")
settings = ConfigResolver().resolve(
    settings_class,
    config_dir=config_dir,
    config_path=Path(config_path) if config_path else None,
)
```

`ConfigResolver.resolve`'s signature is unchanged and already accepts
`config_dir: str | None = None` (`src/lib/buvis/pybase/configuration/resolver.py:261`),
so `config_dir` is passed as the raw string, never a `Path`.

**Precedence between the two, stated rather than assumed:** `resolver.py:187-191`
uses `[config_path] if config_path is not None else find_config_files_ranked(..., config_dir=config_dir ...)`,
so when both are given `config_path` wins absolutely and `config_dir` is
ignored. That is the same behaviour as the wrapper's own resolution
(`click_integration.py:325-330`), and a `--config F --config-dir D` test pins it.

**Known divergence, accepted:** on a group, `patched_group_parse_args` passes
the FULL argv (`click_integration.py:196-203`), so for
`tool --config A sub --config B` the extractor returns `B` while Click binds `A`
to the root group's `--config`. Last-wins matches Click within one command
level only. Accepted for a pre-parse check whose only output is a boolean
opt-out: the scan stops at the `--` sentinel, and a wrong pick here can only
read the wrong config file for the update decision, never change the command's
own configuration. Recorded in Risks.

**3. The global env opt-out must keep working (the second CRITICAL).** Closes:
the design-gate regression above - `BUVIS_AUTO_UPDATE=false` is ignored for any
tool with its own `env_prefix`, breaking PRD Success Metric 2 and two
`tests/tools/dot` isolation tests.

The tool settings class stays the YAML authority (it is what discovers
`buvis-<tool>.yaml`), and the global env var is a **fallback**, never an
override: the tool-prefixed variable is more specific and must win, or
`BUVIS_SYSUP_AUTO_UPDATE=false` (used at `tests/tools/sysup/conftest.py:19`)
would lose to an exported `BUVIS_AUTO_UPDATE=true`.

```python
_GLOBAL_AUTO_UPDATE_ENV = "BUVIS_AUTO_UPDATE"

def _update_enabled(settings_class: type[GlobalSettings], settings: GlobalSettings) -> bool:
    """Whether the passive update check may run.

    The tool's own ``<PREFIX>AUTO_UPDATE`` / YAML value decides. The global
    ``BUVIS_AUTO_UPDATE`` applies only when the tool-prefixed variable is
    absent, so the more specific knob always wins.
    """
    env_prefix = settings_class.model_config.get("env_prefix", "BUVIS_")
    if f"{env_prefix}AUTO_UPDATE" in os.environ:
        return settings.auto_update
    if _GLOBAL_AUTO_UPDATE_ENV in os.environ:
        return GlobalSettings().auto_update
    return settings.auto_update
```

`GlobalSettings` is already imported (`click_integration.py:22`); `os` must be
added to the module imports. The `GlobalSettings()` call can raise pydantic's
`ValidationError` on a malformed value (`BUVIS_AUTO_UPDATE=maybe`), so it runs
inside the guarded block of §4, never outside it - today that read is covered
by `contextlib.suppress(Exception)` and a typo must not start crashing
`tool --help`.

**4. Narrowed failure suppression.** Closes: `R8 🟡 contextlib.suppress(Exception) swallows every exception`.

Only the **settings-decision block** is narrowed, and it covers the resolution
and the env read together:

```python
import logging
import os

from pydantic import ValidationError

from .exceptions import ConfigurationError, MissingEnvVarError

logger = logging.getLogger(__name__)
...
try:
    settings = ConfigResolver().resolve(settings_class, config_dir=config_dir, config_path=...)
    enabled = _update_enabled(settings_class, settings)
except (ConfigurationError, MissingEnvVarError, ValidationError, OSError):
    logger.debug("skipping update check: unresolved configuration", exc_info=True)
    return
```

Four facts this clause rests on, each verified:

- `click_integration.py` has **no logger today** (`rg -n 'logger|logging' src/lib/buvis/pybase/configuration/click_integration.py` is empty), so the `import logging` + `logger = logging.getLogger(__name__)` lines above are part of the change, not assumed. Stdlib logging is allowed in library code; console output from the library is not.
- `resolve` wraps `OSError`/`UnicodeError` (`resolver.py:213-214`) and `ValidationError` (`resolver.py:288-299`) into `ConfigurationError`, so those are belt-and-braces, not required - `MissingEnvVarError` (`exceptions.py:22`) is a bare `Exception` that is *currently always* wrapped (its message at `loader.py:405` never carries the path prefix `resolver.py:207-210` re-raises on), so it is named defensively because that re-raise is message-shape dependent; and `find_config_files_ranked` calls `Path.cwd()`/`Path.home()` outside any per-path guard (`loader.py:181,209-215`), so the wider tuple is deliberate.
- `ValidationError` must be imported; the module imports only `BaseModel` and `FieldInfo` from pydantic today, so an unimported name here would `NameError` on the first failure - worse than the current broad suppress.
- `GlobalSettings()`'s env read sits inside this `try`, which is what makes `BUVIS_AUTO_UPDATE=maybe` a skipped check rather than a raw pydantic traceback on every command.

**The update call keeps a broad guard, deliberately.** `check_and_update` runs
network and subprocess work (`updater/index.py`, `updater/detector.py`) inside
`click.Command.parse_args`, so an unguarded failure there would crash every
CLI invocation including `--help`. It stays wrapped:

```python
if not enabled:
    return

with contextlib.suppress(Exception):
    from buvis.pybase.updater import check_and_update

    check_and_update(settings)
```

A `SystemExit`/`KeyboardInterrupt` still propagates from the resolution block
(`contextlib.suppress(Exception)` does not catch `BaseException`).

## Data flow

`tool [--config F] [--config-dir D] ...` -> patched `Command/Group.parse_args`
-> `_run_update_check_once(ctx, args)` -> `_extract_option_value(args, "--config")`
and `_extract_option_value(args, "--config-dir")` -> `ConfigResolver().resolve(settings_class, config_dir=..., config_path=...)`
-> `_update_enabled(settings_class, settings)` gates `check_and_update(settings)`. The root context's
`_BUVIS_META_CHECKED_KEY` flag still makes this run at most once per invocation,
so the command's own later resolution in `wrapper` does not re-trigger it.

## Reuse inventory

- `ConfigResolver.resolve(settings_class, config_dir=None, config_path=None, cli_overrides=None)` - `src/lib/buvis/pybase/configuration/resolver.py:261`. Already supports `config_dir`; the fix is to pass it, not to add it.
- `_extract_config_path` - `click_integration.py:132`. Existing argv scanner with the `--` sentinel already handled; generalised rather than duplicated.
- `_contains_update_option` - `click_integration.py:~85`. The sentinel-handling precedent `_extract_option_value` follows.
- `ConfigurationError` - `src/lib/buvis/pybase/configuration/exceptions.py`. `resolve` wraps `OSError`/`UnicodeError` (resolver.py:213-214) and pydantic `ValidationError` (resolver.py:288-299) into it. `ValidationError` (pydantic) and `MissingEnvVarError` still need importing for the except tuple; Interfaces §4 says why each is named.
- `GlobalSettings` - already imported at `click_integration.py:22`; supplies the `BUVIS_`-prefixed global env read for the opt-out.
- Nothing found for a generic argv option reader outside this module; greps tried: `rg "def .*(extract|parse_arg|option_value|from_argv)" src/lib/buvis/pybase` (only the four hits above), `rg "config_dir" src/lib/buvis/pybase/configuration` (resolver + wrapper plumbing only).

## Alternatives considered

1. **Smallest diff: revert the signature to `(ctx)` and stash argv in `ctx.meta`.** Makes the sysup/dot stub arity-correct again with no test edits. Rejected: it hides argv in context metadata, which is harder to read than a parameter, and leaves the `--config-dir` and last-wins gaps untouched. The arity break is worth fixing loudly because the stub was a hidden coupling nobody saw.
2. **Chosen: keep `(ctx, args)`, fix the stub with a CLI smoke guard, generalise the extractor, restore the global env read, narrow only the resolution's suppression.** Smallest change that closes the CRITICAL and the 4/4 HIGH together, keeps the signature honest about its inputs, and adds an arity-contract test so the same hidden coupling cannot break silently again.
3. **Full PRD-literal move: run the check inside `wrapper` after `ConfigResolver.resolve`, with an eager-flag pre-pass.** This is what the PRD's text says and it removes the double resolution (R6/R7) outright. Rejected for this cycle: `--help`/`--version` exit eagerly before `wrapper` runs, so a pre-pass is still needed, and the restructuring touches the decorator body that every tool depends on - more risk than the cycle's CRITICAL warrants. The extra size would buy only the removal of one duplicate resolution; R6/R7 stay recorded and the deviation is documented in the docs line instead.

## Risks & edge cases

- `--config` wins over `--config-dir` inside `ConfigResolver.resolve` (resolver.py:187-191); the early check must not invent its own ordering.
- Across a group's argv, last-wins diverges from Click's binding (`tool --config A sub --config B`); accepted and bounded, see Interfaces §2.
- `--config-dir` with no value as the final argv element: `_extract_option_value` must return `None`, not raise.
- `--` sentinel followed by a literal `--config-dir` argument must be ignored.
- The two test suites fail for **two different reasons**: `tests/tools/sysup` from the stub arity, `tests/tools/dot` from the lost `BUVIS_AUTO_UPDATE` env opt-out. Fixing only one leaves the other red.
- The global `BUVIS_AUTO_UPDATE` branch fires only when the tool-prefixed variable is absent, so `BUVIS_AUTO_UPDATE=true` plus YAML `false` runs the check while `BUVIS_DOT_AUTO_UPDATE=false` suppresses it whatever the global says.
- "Env wins over YAML" is **not** a general property of the resolver: `_merge_overrides` (`resolver.py:218-232`) applies a YAML key whenever the field still equals its default, so an env value equal to the default is indistinguishable from unset (measured: `BUVIS_DOT_AUTO_UPDATE=true` plus YAML `false` resolves to `False`). That resolver hole is why this design special-cases the one documented global var; fixing `_merge_overrides` is out of scope for this cycle.
- `_extract_option_value` semantics pinned here, not left open: a trailing bare `--config` does **not** clear an earlier value (last *valued* occurrence wins), and an empty value (`--config-dir=`) is treated as absent, because `Path("")` expands to the cwd inside `loader.py:208` and would silently read cwd config.
- The early check runs before Click validates `--config-dir`'s `exists=True`, so a nonexistent directory is resolved here; it degrades to a skipped check and Click reports the real error moments later.
- `MissingEnvVarError` escaping `resolve` unwrapped depends on its message shape (`loader.py:405` never path-prefixes it); the except tuple names it so a future message change cannot turn into a CLI crash.
- Likely next changes: moving the check fully into `wrapper` (alternative 3), and adding CLI-override awareness to the early resolution. Neither is boxed in: `_extract_option_value` is generic, and the check stays a single call site.

## Test strategy outline

- `test_sysup_cli_runs_with_the_update_check_stub_installed` - the stub-arity guard, fail-first against the current stub.
- `BUVIS_AUTO_UPDATE=false` with a tool whose settings class carries its own `env_prefix` suppresses the check (this is the `tests/tools/dot` isolation case; the two existing tests at `tests/tools/dot/test_filter_cli.py:348` are themselves the regression test and must go green).
- `BUVIS_AUTO_UPDATE=true` with YAML `auto_update: false` runs the check (global env fallback applies when no tool-prefixed var is set).
- `BUVIS_AUTO_UPDATE=true` plus `BUVIS_DOT_AUTO_UPDATE=false` suppresses the check (the specific knob wins).
- `BUVIS_AUTO_UPDATE=maybe` skips the check and does not raise (`tool --help` exits 0).
- `--config-dir=` (empty) and `--config A --config` (trailing bare) behave as pinned in Risks.
- `--config-dir DIR` holding `auto_update: false` suppresses `check_and_update`; `true` calls it. CliRunner, `check_and_update` patched, no network.
- Default discovery: `buvis-<tool>.yaml` / `config.yaml` with `auto_update: false` suppresses the check (the PRD's verbatim evidence case), and `updater.json` is untouched.
- `--config F --config-dir D` together: `F` decides.
- Repeated `--config A --config B`: the value from B decides, matching Click.
- `--config=VALUE` form and the `--` sentinel.
- A malformed config file skips the check and does not crash; an exploding `check_and_update` does not change the command's exit code.
- Gate: run `pytest tests/lib/pybase tests/tools/sysup tests/tools/dot` and report the counts. The cycle-1 narrow gate (`tests/lib/pybase/configuration` + `updater` only) is what hid both regressions, so the rework gate must include the two tool suites.

## Review log

Non-blockers and questions recorded, not fixed this cycle:

- non-blocker (dispatch 1): a skipped update check left no trace - addressed in Interfaces §4 with a module logger the change itself adds.
- non-blocker (dispatch 1): `R6`/`R7` double resolution remains; alternative 3 is the fix and is deferred with its rationale.
- question (dispatch 1): the CHANGELOG entry already landed at cycle 1 - answered in Module placement.
- non-blocker (dispatch 2): "env wins over YAML" is not a general resolver property (`_merge_overrides` default-equality hole) - recorded in Risks, resolver fix out of scope.
- non-blocker (dispatch 2): `MissingEnvVarError` escapes `resolve` unwrapped only by message-shape accident - named in the except tuple and recorded in Risks.
- non-blocker (dispatch 2): three undecided `_extract_option_value` argv shapes - all three pinned in Risks and the test strategy.
- question (dispatch 2): the sysup guard file was missing from Module placement - added.

- non-blocker (dispatch 3): `in os.environ` is case-sensitive while pydantic's env read is not, so a lowercase `buvis_dot_auto_update` would not be seen by `_update_enabled`. Recorded; the documented variables are uppercase and a case-insensitive scan is a follow-up.
- non-blocker (dispatch 3): the global-env fallback reads no YAML, so `BUVIS_AUTO_UPDATE=true` plus YAML `false` runs the check. That is the stated precedence; making the fallback provenance-aware via `ConfigResolver._sources` is a follow-up, out of scope for closing this cycle's CRITICALs.

dispatch 1 (claude): cardinal-sin 0, blocker 4, non-blocker 4, question 1
dispatch 2: codex unavailable, Claude fallback (codex read-only sandbox could not read any file: `sandbox-exec: sandbox_apply: Operation not permitted`, so it substantiated no findings)
dispatch 2 (claude-fallback): cardinal-sin 0, blocker 3, non-blocker 3, question 1
dispatch 3: codex unavailable, Claude fallback (same sandbox failure)
dispatch 3 (claude-fallback): cardinal-sin 0, blocker 1, non-blocker 4, question 0

All seven earlier blockers verified CLOSED by dispatch 3; its one new blocker (the docs replacement sentence stated the env precedence inverted) is fixed in Module placement, and its three consistency non-blockers are fixed in Data flow, Interfaces §4 and the Reuse inventory.

result: ok
