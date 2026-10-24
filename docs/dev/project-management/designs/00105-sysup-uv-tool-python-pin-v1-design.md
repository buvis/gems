# sysup uv-tool-python: design draft

Source PRD: `docs/dev/project-management/prds/wip/00105-sysup-uv-tool-python-pin-v1.md`. This draft refines implementation contracts; the PRD and its acceptance criteria remain unchanged.

## Architecture fit

Add one built-in sysup capability beside `PipxPython`, using the existing `Capability` protocol and `StepResult` generator seam. Configuration selects it through `CAPABILITIES`; `Runner._run_use` already handles dry runs, result stamping, run logs, and controlled exception reporting. CLI, attention, and persistence behavior need no new implementation.

The root `AGENTS.md` and `docs/dev/project-management/meta/project-capsule.md` govern placement and interface separation. The older `docs/dev/context/project-capsule.md` supplies background only. No nested `AGENTS.md` exists in this checkout; the optional cartographer atlas is absent. Reuse the sibling's orchestration pattern without importing its private helpers or refactoring it.

## Module placement

| Path | Change |
| --- | --- |
| `src/tools/sysup/capabilities/uv_tool_python.py` | New capability and its private discovery/version helpers. |
| `src/tools/sysup/capabilities/__init__.py` | Import `UvToolPython`; register its instance under `uv-tool-python`. |
| `src/tools/sysup/default.yaml` | Add the independent order-35 entry before the existing order-40 uv entry. |
| `tests/tools/sysup/test_uv_tool_python.py` | New class-based tests with temporary receipt trees and fake subprocess calls. |
| `tests/tools/sysup/test_default_config.py` | Update the exact Darwin plan and assert entry order, guard, use name, and unchanged uv steps. |
| `docs/source/tools/sysup.rst` | Describe pinning, failure recovery, and safety skips in the capabilities/configuration documentation. |
| `CHANGELOG.md` | Add the PRD's sysup item under `[Unreleased] / Added`. |

`tests/tools/sysup/test_invariants.py` already globs every capability module and needs no edit. No new dependency, CLI option, public library API, receipt writer, or runner behavior is needed.

## Interfaces & contracts

The new module exports exactly `__all__ = ["UvToolPython"]`. Use modern type annotations, `TYPE_CHECKING` imports for `Iterator`/`Mapping`, stdlib `tomllib`, argv subprocess calls, and no direct output or process exit.

```python
_MINOR = re.compile(r"^(\d+\.\d+)")

def _tool_dir(uv: str) -> Path: ...
def _global_minor(mise: str) -> str | None: ...
def _pinned_minor(receipt_path: Path) -> str | None: ...

class UvToolPython:
    @property
    def inputs(self: UvToolPython) -> Mapping[str, object]: ...

    def run(self: UvToolPython, **kwargs: object) -> Iterator[StepResult]: ...

    def _move(
        self: UvToolPython, uv: str, tool: str, old: str | None, target: str
    ) -> StepResult: ...
```

`inputs` returns `{}`: this PRD introduces no `with:` keys. `run` resolves `uv` and `mise` using `shutil.which` on each invocation. Missing either yields exactly one `StepResult("uv tool python", success=False, message="uv or mise not found, skipping")` and stops. `_global_minor` runs `[mise, "current", "python"]` with `cwd=Path.home()`, `capture_output=True`, `text=True`, `check=False`; a nonzero result or unmatched stripped stdout returns `None`. That produces `success=False`, message `no global mise python version, skipping`, and no install command.

`_tool_dir` runs `[uv, "tool", "dir"]` with captured text and `check=False`. Use a successful nonempty stripped path; otherwise use nonempty `$XDG_DATA_HOME/uv/tools`, otherwise `Path.home() / ".local/share/uv/tools"`. Do not create the directory. A missing root is empty; a root that exists but cannot be listed yields a failed discovery result, not a false no-tools success. Enumerate sorted immediate subdirectories only; ignore files and dot-prefixed metadata directories. Resolve receipt names from directory names without invoking a shell.

`_pinned_minor` reads `uv-receipt.toml` with `tomllib`, requires a `[tool]` table, and returns the leading `X.Y` from a supported numeric version string. An absent `python` key alone returns `None`. Compare minor tuples `(int(major), int(minor))`, never strings: move an absent pin or one below the target; leave equal and newer pins untouched. This follows the PRD's “below the global” predicate rather than copying the sibling's `!=` predicate, which could downgrade a deliberate newer pin.

Safety preflight is part of `_pinned_minor`, before any reinstall. A bare-name reinstall is supported only for a receipt whose original request is that same normalized package name with no customization: `requirements` is exactly `[tool_name]` in the legacy string form or `[{"name": tool_name}]` in uv's structured form; normalize names by lowercasing and collapsing `[-_.]+` to `-`. Explicitly empty `extras` and empty `specifier` in that single structured requirement are also harmless. `constraints`, `overrides`, `excludes`, and `build-constraint-dependencies` must be absent or empty; `options` must be absent or `{}`. Allow uv-owned `entrypoints` metadata but reject an entrypoint with a nonempty `from` naming a different package. Unknown substantive keys in `[tool]` or the requirement object are unsupported. These checks ensure the PRD's bare `<tool>` argv cannot discard an original source, extras, dependency injection, index, constraint, or resolver option.

Missing/malformed receipts, a missing requirements identity, unsupported customizations, and a present `python` that is not a numeric version are distinguishable failures, never silently treated as an unpinned plain package. Catch `OSError`, `tomllib.TOMLDecodeError`, and validation `ValueError` per tool, yield `StepResult(tool, success=False, message="<reason>, skipping")`, and continue other tools. Numeric selectors match `\d+\.\d+(?:\.\d+)?` with an optional prerelease suffix; selectors such as `pypy@3.10`, `cpython@3.14`, paths, executable names, ranges, and free-threaded `3.14t` remain untouched with an explicit unsupported-selector failure. Do not add selector resolution or a general receipt-to-argv translator in this PRD.

This is a deliberate safety refinement of the PRD's malformed-receipt fallback: without readable installation intent, a bare package reinstall cannot guarantee recovery. It changes no acceptance criterion or named scenario; it reports the unsupported case visibly instead of claiming that parsing failure proves an ordinary unpinned install.

If the root has no candidate tools, yield exactly one successful result with message `no uv tools installed`. If all safely read pins equal the target, yield exactly one successful result with message `all uv tools on python <target>`. If there are only equal/newer pins and at least one newer pin, use the truthful message `all uv tools pinned to python <target> or newer`. Never emit an all-current success when any receipt was skipped with failure. When there are eligible moves, run `[uv, "python", "install", target]` once before the first move. If it fails, yield one failed result containing `uv python install <target> failed: <stderr-or-unknown error>` and stop without tool installs.

`_move` returns one `StepResult` labelled `<tool> (python <old-or-unpinned> -> <target>)`. Its initial argv is exactly `[uv, "tool", "install", "--python", target, "--force", tool]`. On exit zero, return success. On nonzero exit or `OSError`, attempt rollback for that tool: `[uv, "tool", "install", "--python", old, "--force", tool]` when previously pinned, or `[uv, "tool", "install", "--force", tool]` when previously unpinned. All installs capture text and use `check=False`. Do not edit receipts directly; uv owns its environment and receipt writes. Continue processing later tools after either outcome.

Only a zero rollback exit permits `kept on python <old>` or `kept unpinned` in the failed result. A failed rollback reports `reinstall on python <old> also failed` or `unpinned reinstall also failed`, including both initial and rollback diagnostics. Never claim a working tool after failed recovery. Use `stderr.strip()` with `unknown error` fallback for nonzero commands. An `OSError` supplies its exception text. Unpinned rollback restores absence of an explicit request, not necessarily the identical historical interpreter; no stronger recovery claim is made. Recovery of exact package versions, or an environment snapshot, is outside this PRD's contract.

The registry addition is exactly `"uv-tool-python": UvToolPython()`. Preserve the registry module's current `__all__` public surface. Add this bundled command entry:

```yaml
  # Pin freestanding uv tools to the global python minor before uv tool upgrade.
  uv-tool-python:
    order: 35
    when: { os: darwin, check: uv }
    use: uv-tool-python
```

Keep `uv.order == 40` and its steps exactly `(("uv", "python", "upgrade"), ("uv", "tool", "upgrade", "--all"))`. Before implementation, recheck that premise; if it changed, stop and report as the PRD requires. No command dependency or fail-fast policy is added: this capability reports failed tools while the existing runner continues its normal plan.

## Data flow

1. The existing config loader merges defaults and host overrides; its applicable-command sorter places `uv-tool-python` between `python-packages` and `uv` on Darwin.
2. The runner selects the registered capability; dry run reports it without calling `run`.
3. The capability resolves binaries and the global mise minor from `$HOME`, discovers the uv tools root, and reads each receipt without writing it.
4. Receipt validation separates plain reproducible installations from unsafe or unreadable cases. Minor comparison separates eligible moves from current/newer pins.
5. One interpreter preparation precedes eligible installs. Each install produces one final result after any rollback, and later tools continue.
6. Existing runner stamping, attention, and CLI rendering consume the results. The existing order-40 uv entry subsequently performs its two upgrades.

The selected target is the global minor present at order 35. Mise's order-60 upgrade may change it later in the same run; adoption then occurs next run. Reordering mise or changing `uv python upgrade` is out of scope.

## Reuse inventory

Sweep completed before drafting, using the present `~/.claude/rules-library/rationalizations.md` verb/noun synonym guidance.

| Existing helper/pattern | How to use it |
| --- | --- |
| `src/tools/sysup/capabilities/pipx_python.py:PipxPython.run`, `._global_minor`, `._move`, `_MINOR` | Follow binary guards, HOME-scoped target lookup, one-time interpreter preparation, per-tool results, and recovery reporting. Keep backend-specific logic local; do not import private sibling symbols. |
| `src/tools/sysup/capabilities/__init__.py:Capability`, `CAPABILITIES` | Implement the existing structural protocol and add one registry instance. |
| `src/tools/sysup/step_result.py:StepResult` | Yield immutable standard results; `success=False` already sets status to `failed`. |
| `src/tools/sysup/runner.py:Runner._run_use` | Reuse dry run, command stamping, run-log integration, and exception containment unchanged. |
| `src/tools/sysup/config.py:load_config`, `applicable_commands` and `default.yaml` | Reuse validation, layered overrides, OS/binary guard, and numeric ordering. |
| `tests/tools/sysup/test_pipx_python.py:TestPipxPython._fake_run` | Mirror fake argv dispatch and first-failure tracking with temporary uv receipt fixtures. |
| `tests/tools/sysup/test_default_config.py:_plan_names`, `TestDefaultConfigEquivalence` | Extend exact Darwin plan and check the new entry without weakening Linux assertions. |
| `tests/tools/sysup/test_invariants.py:_LIBRARY_FILES` | Existing capability glob automatically checks the new module. |
| `src/lib/buvis/pybase/filesystem/atomic_write.py:atomic_write_text` | Existing persistence invariant reviewed; unnecessary here because only uv writes receipts. |

Exact search families run:

- Verb synonyms: `rg -n 'parse|decode|load|read|find|lookup|resolve|select' src/tools/sysup/capabilities src/tools/sysup/config.py src/tools/sysup/runner.py` located existing discovery/parsing seams.
- Noun and action synonyms: `rg -n -g '*.py' 'global_minor|_MINOR|reinstall|restore|rollback|revert' src/tools/sysup tests/tools/sysup` located the sibling and its tests.
- uv receipt/root helper: nothing found, greps tried: `rg -n -g '*.py' 'uv-receipt|uv tool dir|UV_TOOL_DIR|XDG_DATA_HOME' src tests tools`. Empty output was checked with `rg -n -g '*.py' 'pipx_python|current.*,.*python|subprocess.run' src/tools/sysup/capabilities tests/tools/sysup/test_pipx_python.py`, which returned the known sibling and subprocess sites.
- Persistence/parser nouns: `rg -n 'atomic_write|tomllib|XDG_DATA_HOME|UV_TOOL_DIR' src/lib src/tools/sysup tests/tools/sysup` found atomic writes and stdlib TOML parsing precedent, but no uv receipt parser to reuse.

Primary uv checks: local `uv 0.13.5` help confirms install/upgrade Python flags; [uv's tool model](https://github.com/astral-sh/uv/blob/main/crates/uv-tool/src/tool.rs) records requirements and options, and [install logic](https://github.com/astral-sh/uv/blob/main/crates/uv-tool-commands/src/install.rs) constructs the request from current install inputs. Therefore bare-name install must not be assumed to replay custom receipt intent. [Storage documentation](https://docs.astral.sh/uv/reference/storage/#tools) confirms `uv tool dir` as the authoritative root query.

## Alternatives considered

1. **Smallest diff: transpose `PipxPython`, reinstall every discovered directory by bare package name.** This fits ordinary tools and the seven named cases, but can discard custom sources/dependencies/options, overwrite non-version selectors, downgrade newer pins, and misreport recovery. Reject that unchecked form.
2. **Chosen: the sibling pattern plus bounded receipt validation and truthful recovery.** Keep the PRD's install argv, order-35 entry, and independent capability. A small preflight skips installations whose intent cannot survive that argv. No replay framework or sibling refactor is needed. Customized receipts remain visibly unresolved rather than silently changed.
3. **Use `uv tool upgrade --python`, or implement complete receipt replay/environment backups.** Native upgrade is attractive for retaining uv-owned intent but changes the PRD's explicit reinstall/revert argv acceptance; full replay adds a second evolving receipt implementation. Both are deferred to a later requirement instead of expanding this PRD.

## Risks & edge cases

- Unknown/customized or malformed receipts stay unresolved and can still fail the subsequent batch upgrade. The design exposes this as failure; automatic repair without installation intent is not safe. This bounded coverage is explicit, while the seven PRD acceptance scenarios remain supported.
- A numeric patch pin is classified by its minor and rollback requests that prior minor, as specified by the PRD. A newer pin is preserved. A range, path, implementation-specific, or free-threaded request is not interpreted as ordinary CPython.
- A failed install can be followed by a failed rollback. Both errors must remain visible, and no successful recovery is claimed. Unpinned reinstall can select a different interpreter; this v1 restores unpinned policy rather than promising an identical environment.
- Directory fallback applies only when the root query fails or is empty. Permissions, malformed files, or unexpected schema must not become a successful empty inventory. Do not read recursively or mutate metadata entries.
- uv commands own environment locking; this capability adds no concurrent scheduler or receipt mutation. A simultaneous external install can race discovery. Avoid overwriting receipt metadata directly; a later concurrency requirement would need a separate coordinated design.
- Likely next changes are custom-receipt support through a confirmed uv-native operation, selector-aware handling, and sharing version-discovery logic with `PipxPython`. Local helpers and unchanged registry/runner seams allow these later changes without committing to a generic replay abstraction now.

## Test strategy outline

Keep all seven PRD-named tests, with real-shaped plain receipts under `tmp_path`: unpinned move, stale move, current pin no-op, failed move plus pinned/unpinned rollback, no tools, no global Python, and missing binaries. Mock every subprocess and `shutil.which`; never install an actual host tool or edit host receipts.

Add focused safety cases: numeric tuple comparison (`3.9` versus `3.14`), newer pin unchanged, patch version minor extraction, unsupported selectors unchanged, customized source/extras/with/options/constraints untouched, malformed/missing receipt fails safely, fallback root selection, interpreter-preparation failure, rollback failure including both diagnostics, `OSError` recovery, and later-tool continuation. Assert absence of mutating argv for skipped/current/newer tools, not only message text. Include a modern plain requirement receipt and its legacy form.

Wiring tests assert `CAPABILITIES["uv-tool-python"]` implements `Capability`, the exact Darwin plan includes it before uv, order is 35, guard is Darwin plus `uv`, Linux excludes it, and existing uv argv remains unchanged. The invariant test's existing glob needs no extra list.

Required implementation checks remain those in the PRD: `uv run pytest tests/tools/sysup/test_uv_tool_python.py -q`; `uv run pytest tests/tools/sysup/test_default_config.py -q`; `uv run pytest tests/tools/sysup/test_invariants.py -q`; `uv run pytest -m sysup -q`; `uv run mypy src/tools/sysup`; `uv run ruff check src/tools/sysup tests/tools/sysup/test_uv_tool_python.py`; `uv run sphinx-build -b html docs/source docs/build/html -q`; and the PRD's documentation/changelog searches. This draft does not execute implementation tests or change acceptance criteria.

## Review log
dispatch 1 (claude): cardinal-sin 0, blocker 0, non-blocker 1, question 1
Host provenance: native gpt-6.1-sol/high, isolated dispatch design_review_1; source claude label is a schema role only. Initial review plus one minimum-engagement retry provided section-anchored checks.
Non-blocker: qualify universal documentation guarantees because customized/unreadable receipts remain unchanged and may still fail a later upgrade.
Question: optional prerelease suffix grammar is unspecified; use a full-string match and test valid prerelease versus trailing junk.
dispatch 2: codex unavailable, Claude fallback
dispatch 2 (claude-fallback): cardinal-sin 0, blocker 0, non-blocker 0, question 1
Host provenance: role-swapped external Claude sonnet/high failed authentication (raw evidence: reports/00105-design-external-auth-failure.txt); fresh native gpt-6.1-sol/high fallback performed review and one minimum-engagement retry. No third dispatch required.
Question: unknown substantive receipt keys need an exact definition; conservative implementation rejects every unknown key, including empty values.

Design exit: 2/3 dispatches; cardinal-sin 0, blocker 0, non-blocker 1, question 2; no open cardinal sins/blockers; no weak dispatches; result ok.
