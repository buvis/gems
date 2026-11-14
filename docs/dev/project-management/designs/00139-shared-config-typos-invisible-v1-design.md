# Design: Typos in shared config files are never reported

## Architecture fit

Lands entirely in `src/lib/buvis/pybase/configuration/` (the `ConfigResolver`
layer) plus packaging metadata in `pyproject.toml`. `ConfigResolver._load_yaml`
(`resolver.py`) already special-cases `config.yaml`/`buvis.yaml` by name to
skip the `extra="forbid"` projection check (`known_keys` ignored for those two
names) - this design replaces that silent skip with a warn-only check,
keeping the Key Invariant "Commands return `CommandResult`; ... No
print/click.echo/logging" intact by using the module's existing `logger`
(library code, not command layer - this file already logs via
`logger.debug`/`logger.info`, never `print`/`console`).

**Existing convention this design must respect (confirmed in
`docs/source/configuration.rst:106-122` and
`tests/lib/pybase/configuration/test_tool_config_keys.py::test_shared_config_keeps_other_tool_namespaces`):**
a shared file does **not** carry other tools' fields flat at the top level.
It carries a `<tool>:` **namespace section** per other tool (e.g. `sysup:
{commands: {...}}`, `bim: {path_zettelkasten: ...}` inside `buvis.yaml` while
resolving `BraidSettings`) - that section is "not projected onto that tool"
(docs:119-121) and is simply ignored by every *other* tool's resolve(),
exactly as today, unchanged by this design. The PRD's own evidence
(`srouces:` instead of `sources:` in braid's *own* config) is a typo in the
**resolving tool's own flat field**, not a cross-tool field collision - the
bug is that `config.yaml`/`buvis.yaml` skip even the resolving tool's own
known-key check, which an arbitrary/custom filename does not skip.
Consequently the check this design adds needs to recognize two things as
valid, not one: (a) the resolving tool's own fields/deferred keys - already
computed as `known_keys`, no change needed - and (b) **any top-level key
that is a registered tool's name** (a legitimate, if currently-irrelevant,
`<tool>:` namespace section belonging to some *other* tool). It does **not**
need any other tool's *field names* - those stay opaque inside that tool's
own namespace section, exactly as `test_other_tool_files_are_not_validated`
already proves for a dedicated `buvis-sysup.yaml` with intentionally broken
YAML.

The registry itself is a new library module,
`src/lib/buvis/pybase/configuration/registry.py`, that discovers every
installed tool's **name** through the standard Python **entry-points**
mechanism (`importlib.metadata.entry_points`), never through an `import
<tool_package>` statement and, per the simplified scope above, **without
ever calling `ep.load()`** - an entry point's `.name` is metadata-only
information `importlib.metadata` already parses to list the group, so no
tool module is imported at all, not even optionally. This satisfies the
AGENTS.md invariant "the library stays interface-agnostic ... must not
import a UI framework [or tool code] at module import time" more strongly
than the original approach: the library names a *group*, not a *tool*, and
never executes a byte of tool code to answer this check; tools opt in by
declaring themselves in `pyproject.toml` packaging metadata, which is data,
not library code.

## Module placement

- **New file** `src/lib/buvis/pybase/configuration/registry.py` - the
  entry-point name discovery.
- **Edit** `src/lib/buvis/pybase/configuration/resolver.py` -
  `ConfigResolver._load_yaml` replaces the by-name full exemption with a
  warn-only check for `config.yaml`/`buvis.yaml`.
- **Edit** `src/lib/buvis/pybase/configuration/__init__.py` - export nothing
  new publicly; `registry.known_tool_names` is an internal helper used only
  by `resolver.py` (keep the public surface unchanged, per Simplicity).
- **Edit** `pyproject.toml` - one new entry-point group,
  `[project.entry-points."buvis.config_settings"]`, with one line per tool
  package that already appears in `[tool.hatch.build.targets.wheel].packages`
  (18 lines, mirroring that list exactly - confirmed by reading
  `pyproject.toml`, no wheel-packages edit needed).
- **No edits** to any `src/tools/*/settings.py` - every existing
  `<Tool>Settings` class is already the entry-point target; none change
  shape.
- `docs/source/configuration.rst` - document the new warn-only shared-key
  check and the entry-point registration contract for a new tool.
- `CHANGELOG.md` - `Fixed` entry.

## Interfaces & contracts

### `src/lib/buvis/pybase/configuration/registry.py` (new)

```python
"""Cross-tool name discovery for the shared config-file typo check.

Discovers every installed tool's *name* through the
``buvis.config_settings`` entry-point group, never by importing a tool
package - see AGENTS.md "the library stays interface-agnostic". A tool's
name is the ``<tool>:`` namespace key a shared config file may legitimately
carry for it (``docs/source/configuration.rst`` "Tool-Specific Configuration
Files"); this module answers only "is this a registered tool name", nothing
about any tool's own fields.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import entry_points

__all__ = ["CONFIG_SETTINGS_ENTRY_POINT_GROUP", "known_tool_names"]

CONFIG_SETTINGS_ENTRY_POINT_GROUP = "buvis.config_settings"


@lru_cache(maxsize=1)
def known_tool_names() -> frozenset[str]:
    """Every registered tool's entry-point name.

    Reads only ``EntryPoint.name`` - never calls ``.load()`` - so this
    function imports no tool code at all, not even optionally; it is pure
    distribution metadata lookup. A shared config file's `<tool>:` section
    for a tool missing from this set (uninstalled extra, not yet
    registered) is indistinguishable from a genuine typo and surfaces as a
    noisy warning rather than silence (see PRD 00139 Risks) - accepted, not
    solved, by this design.

    Cached for the lifetime of the process: ``entry_points(group=...)``
    re-parses every installed distribution's metadata on each call, and
    `_load_yaml` calls this once per `resolve()` call, which runs on every
    CLI invocation of every tool. Uncached, this adds a cross-distribution
    metadata scan to the hot path of every tool command that touches
    `config.yaml`/`buvis.yaml` - unacceptable for a check most users never
    trip. Tests that need a fresh set after monkeypatching `entry_points`
    call `known_tool_names.cache_clear()` first.
    """
    return frozenset(ep.name for ep in entry_points(group=CONFIG_SETTINGS_ENTRY_POINT_GROUP))
```

Cached with `lru_cache(maxsize=1)` (no arguments, so one cached value for
the process). A CLI process is short-lived and the registered tool set
cannot change mid-process, so a process-lifetime cache is correct; tests
that monkeypatch `entry_points` call `known_tool_names.cache_clear()`
first (noted below in Test strategy).

No exception handling is needed here (unlike an earlier revision of this
design that called `ep.load()` to collect per-tool field sets): reading
`.name` off an `EntryPoint` object cannot fail the way importing a tool
module can, so there is no broken-tool failure mode to guard against for
this function. Entry-point *values* (the `module:ClassName` targets below)
are therefore unused by this check; they are still worth pointing at each
tool's real `<Tool>Settings` class for self-documentation and so a future
PRD that does need field-level data has a correct target to load.

### `src/lib/buvis/pybase/configuration/resolver.py` (edit)

`_load_yaml`'s per-file loop currently reads:

```python
if known_keys is not None and path.name not in {"config.yaml", "buvis.yaml"}:
    unknown = [key for key in layer if _split_directive(key)[0] not in known_keys]
    if unknown:
        raise ConfigurationError(f"unknown configuration key(s): {', '.join(sorted(unknown))}")
```

Replace with:

```python
if path.name in {"config.yaml", "buvis.yaml"}:
    for key in layer:
        base = _split_directive(key)[0]
        is_own_field = known_keys is not None and base in known_keys
        is_tool_namespace = base in known_tool_names()
        if not is_own_field and not is_tool_namespace:
            logger.warning(
                "%s: unknown configuration key '%s' - matches neither this "
                "tool's own settings field (or declared deferred key) nor "
                "any registered tool's namespace section",
                path,
                base,
            )
elif known_keys is not None:
    unknown = [key for key in layer if _split_directive(key)[0] not in known_keys]
    if unknown:
        raise ConfigurationError(f"unknown configuration key(s): {', '.join(sorted(unknown))}")
```

- `from .registry import known_tool_names` is a new import at the top of
  `resolver.py` - a same-package library module, not tool code.
- `known_keys` is **unchanged** from today - still the resolving tool's own
  `model_fields | config_deferred_keys`, computed once in `resolve()` and
  passed down, already including every `GlobalSettings` field through
  inheritance (every `<Tool>Settings` subclasses `GlobalSettings`). This
  design adds no new computation for the resolving tool's own keys - it
  only adds the `is_tool_namespace` check, which recognizes a *different*
  tool's `<tool>:` section exactly as the resolver already implicitly
  tolerates it (the key is simply never assigned, since `_merge_overrides`
  only applies keys where `hasattr(base_settings, key)` - unaffected here).
- When `known_keys is None` (the only caller that hits `_load_yaml` with
  `known_keys=None` is a settings class whose `tool_name` could not be
  extracted or whose `model_config` is not `extra="forbid"` - resolving
  `GlobalSettings` directly is the only such case today, not exercised by
  any real tool CLI), `is_own_field` is always `False` and the check falls
  back to tool-namespace recognition alone plus - because every real
  caller's `known_keys` already carries the inherited global fields - no
  `GlobalSettings`-only key would be flagged in practice anyway.
- `_split_directive` (list-merge directives like `sources+:`) is already
  imported in this file; reused unchanged so a directive on a key is
  checked against its base name, matching the existing non-shared-file
  branch. A `<tool>:` namespace section is a plain mapping key, never
  carries a directive suffix, so `is_tool_namespace` only ever needs the
  bare name - using `base` (post-`_split_directive`) for both checks keeps
  one code path instead of two.
- Nothing raises for `config.yaml`/`buvis.yaml` - behavior Success Metric 1
  requires ("Warn (not fail)"); the raising branch now only ever runs for a
  named/explicit file, unchanged from today.
- A `<tool>:` namespace section for any registered tool produces no warning
  (preserves `test_shared_config_keeps_other_tool_namespaces`'s `sysup:`/
  `bim:` sections unchanged); the resolving tool's own typo'd field (the
  PRD's `srouces:` evidence) matches neither `known_keys` nor
  `known_tool_names()` (no tool is named "srouces") and warns, which is
  the bug this PRD fixes.

### `pyproject.toml` (edit)

New section, placed directly after `[project.scripts]`:

```toml
[project.entry-points."buvis.config_settings"]
backup = "backup.settings:BackupSettings"
bim = "bim.settings:BimSettings"
braid = "braid.settings:BraidSettings"
dot = "dot.settings:DotSettings"
fctracker = "fctracker.settings:FctrackerSettings"
fren = "fren.settings:FrenSettings"
klyreon = "klyreon.settings:KlyreonSettings"
morph = "morph.settings:MorphSettings"
muc = "muc.settings:MucSettings"
netscan = "netscan.settings:NetscanSettings"
outlookctl = "outlookctl.settings:OutlookctlSettings"
postup = "postup.settings:PostupSettings"
puc = "puc.settings:PucSettings"
pinger = "pinger.settings:PingerSettings"
readerctl = "readerctl.settings:ReaderctlSettings"
sysup = "sysup.settings:SysupSettings"
vuc = "vuc.settings:VucSettings"
zseq = "zseq.settings:ZseqSettings"
```

One line per `<Tool>Settings` class confirmed to exist in the working tree
(`rg -n "^class .*Settings" src/tools/*/settings.py`, 18 hits). All 18 are
already present in `[tool.hatch.build.targets.wheel].packages` (confirmed by
reading `pyproject.toml`), so no wheel-packages edit is needed - the
entry-point lines above are a one-to-one mirror of that existing list, same
18 names.

**Scaffold contract (follow-on, not required by this PRD):** `tools/lib/scaffold.py`
(new-tool generator) should add the matching `[project.entry-points."buvis.config_settings"]`
line whenever it adds a `[project.scripts]` line and a wheel `packages`
entry, so a newly scaffolded tool self-registers for this check from day
one. Out of scope here (`tools/lib/scaffold.py` is not touched by this PRD);
recorded as a Risk below so a future tool addition does not quietly regress
to the "registry missing a tool" noisy-warning failure mode.

### `docs/source/configuration.rst` (edit)

Extend the existing "Tool-Specific Configuration Files" section (around
line 118-122, which already documents the `<tool>:` namespace convention)
with one paragraph: a top-level key in `config.yaml`/`buvis.yaml` now warns
(never fails) when it matches neither the resolving tool's own settings
field/declared deferred key nor any *registered tool's name* (i.e. it is
not a legitimate `<tool>:` namespace section either) - this is what catches
a typo in the resolving tool's own field (the `srouces:`/`sources:`
example already used elsewhere in this doc, if any - otherwise introduce
it here) without flagging a *different* tool's namespace section. An
explicit or custom-named file (e.g. `--config custom.yaml`) still fails
hard on an unknown key, unchanged. One line noting the entry-point
contract: a new tool is recognized as a namespace owner only once it is
registered under `buvis.config_settings` in `pyproject.toml`.

## Data flow

1. `ConfigResolver.resolve()` calls `_load_yaml()` with the resolving tool's
   `known_keys` (already computed from `settings_class.model_fields |
   config_deferred_keys`, unchanged).
2. `_load_yaml()` iterates the ranked, discovered config files. For each
   layer loaded from a file named `config.yaml` or `buvis.yaml`:
   a. For each top-level key, strip any merge directive to get `base`
      (`_split_directive`, unchanged, already imported).
   b. `base` is valid if it is in `known_keys` (the resolving tool's own
      field or declared deferred key - unchanged from today) **or** it is a
      registered tool's name per `known_tool_names()` (a legitimate
      `<tool>:` namespace section for some *other* tool - `known_tool_names()`
      walks the `buvis.config_settings` entry-point group once, reading
      only `.name`, no module import). Otherwise `logger.warning(...)`
      names the file path and the key. The layer still merges into
      `merged` via `self.loader.merge_configs` exactly as before, and the
      downstream `_merge_overrides` step still drops any key with no
      matching attribute on `base_settings` (a `<tool>:` section never
      becomes an attribute) - a warning never drops or mutates a value, nor
      makes a previously-dropped key start applying.
3. For any other file name, behavior is byte-for-byte unchanged: `known_keys`
   gates a hard `ConfigurationError` on an unknown key; `known_tool_names()`
   is never consulted off the `config.yaml`/`buvis.yaml` path, so a custom
   file still cannot smuggle in another tool's namespace section
   unvalidated (matches `test_rejects_unknown_tool_keys_before_projection`'s
   `"explicit"` layer case, which is not a `config.yaml`/`buvis.yaml`
   filename).
4. Every other step of `resolve()` (merge, `_merge_overrides`, source
   tracking) is untouched; this change is confined to the warn-vs-skip
   decision inside `_load_yaml`'s per-file loop.

## Reuse inventory

- `src/lib/buvis/pybase/configuration/resolver.py::_split_directive` -
  already imported in this file from `.loader`; reused unchanged to strip
  a list-merge directive (`sources+:`) before comparing a key's base name,
  matching the existing unknown-key check for non-shared files.
- `src/lib/buvis/pybase/configuration/resolver.py::ConfigResolver.resolve` -
  already computes `known_keys` for the resolving tool
  (`set(settings_class.model_fields) | set(getattr(settings_class,
  "config_deferred_keys", ()))`); reused as-is, unchanged, as one half of
  the new check's validity test.
- `docs/source/configuration.rst` lines 106-122 and
  `tests/lib/pybase/configuration/test_tool_config_keys.py` - read before
  designing the registry's shape; these are what surfaced the `<tool>:`
  namespace convention and corrected an earlier draft of this design that
  assumed flat cross-tool field merging (see Review log). Without reading
  the existing tests first, this design would have shipped a registry that
  collects every tool's *field names* - wrong scope, and the exact kind of
  mismatch `test_shared_config_keeps_other_tool_namespaces` would have
  caught at implementation time, just later and more expensively than at
  design time.
- grep sweep for an existing cross-tool registry/plugin-discovery mechanism
  before proposing a new one: `rg -n "entry_points|entry－points|register"
  src/lib src/tools` and `rg -n "importlib.metadata" src/lib src/tools` -
  nothing found; no prior registry, decorator-based self-registration, or
  `importlib.metadata` use exists anywhere in the codebase.
- grep sweep for existing "unknown key" / typo-detection code beyond the one
  branch this design replaces: `rg -n "unknown configuration key|unknown
  key" src/lib src/tools` - only the single `ConfigurationError` raise this
  design edits; no parallel implementation to reconcile.

## Alternatives considered

1. **Decorator-based self-registration into a module-level dict**
   (`@register_settings` applied to each `<Tool>Settings` class, writing
   into a `dict` owned by `registry.py`). Rejected: the registry would only
   ever contain the *currently resolving* tool's class, because tool
   packages are imported lazily by each tool's own `cli.py` - no CLI
   invocation imports any other tool's module, so the dict never converges
   to "every tool" within a single process. This directly reproduces
   today's bug (only the current tool's keys are known) rather than fixing
   it; a decorator adds indirection with no behavioral gain.
2. **Smallest-diff option: hardcode the key union as a literal list in
   `resolver.py`,** maintained by hand, verified by a test that compares it
   against each tool's `settings.py` imported directly (tests may import
   tool code; only the library must not). Rejected over the entry-point
   design in favor of the latter, which trades a few `pyproject.toml` lines
   for a mechanism that cannot drift from the *actual* installed tool set:
   a hardcoded list updates only when someone remembers to update it (the
   exact failure mode the PRD's Risks section calls out: "a registry that
   misses a tool"), while entry points fail closed - registration lives
   beside the exact same `[project.scripts]` line a new tool already needs,
   one `git grep project.scripts` away from being impossible to miss in
   review. The entry-point version costs ~20 extra lines in packaging data
   and one new 25-line module; judged worth it for a check meant to run on
   every tool's every `resolve()` call for the lifetime of the project.
3. **Chosen: entry-point discovery (`buvis.config_settings` group), reading
   only `.name` - no tool module import at all, not even via `ep.load()`.**
   Converges to the true installed tool set every time (works identically
   whichever tool's CLI is running), requires no runtime tool import in
   library code (stronger than alternative 2: it never even optionally
   imports a tool module), and reuses Python's own standard plugin
   mechanism rather than inventing one. Its cost (one `pyproject.toml`
   entry per tool) is exactly the kind of addition `tools/lib/scaffold.py`
   already generates peers of (`[project.scripts]`, wheel `packages`) for a
   new tool, so the follow-on work recorded above slots into an existing
   generator rather than a new one. (An earlier revision of this design
   additionally called `ep.load()` to collect every tool's `model_fields`,
   under the mistaken assumption that a shared file merges other tools'
   *fields* flat; reading the existing `<tool>:` namespace convention
   corrected that - this design only ever needs tool *names*, never any
   tool's fields, so `ep.load()` is unnecessary and was removed.)

## Risks & edge cases

- **Registry omission -> noisy warning, not silence.** A tool whose entry
  point is missing or misspelled in `pyproject.toml` means its name is
  invisible to `known_tool_names()`; a shared config file carrying that
  tool's `<tool>:` namespace section then warns on that section's key for
  every *other* tool's CLI invocation (the section's contents are still
  never validated or applied, unchanged - only the top-level key itself
  warns). This is the PRD's own documented Risk ("A registry that misses a
  tool turns valid keys into noisy warnings") - accepted, not solved, by
  this design; mitigated by tying registration to the same
  `[project.scripts]`/wheel-`packages` lines a new tool already cannot
  skip, and by the scaffold follow-on below. Reading only `.name` (never
  `ep.load()`) removes the *other* way a tool could drop out of the
  registry - a broken or heavy import in that tool's `settings.py` can no
  longer silently exclude it, since this design never imports it.
- **The warning is a bare log line until PRD 00140 lands** (PRD's own
  Risk) - `resolver.py` is library code with no `console` dependency (Key
  Invariant: "the library stays interface-agnostic"), so this design adds
  no `console.warning` call; PRD 00140 is explicitly where a structured,
  per-tool-surfaced warning is scoped. In practice, because no `cli.py` in
  this repo installs a logging handler (confirmed: no
  `logging.basicConfig`/handler wiring anywhere in `src/lib`/`src/tools`
  outside the unused `console.py::logging_to_console()` context manager),
  Python's own `logging.lastResort` handler (a `StreamHandler(WARNING)` to
  stderr) already prints this `logger.warning(...)` call to the terminal
  today - so the PRD's "bare log line" framing undersells what ships here;
  this design satisfies the PRD's success metrics as a visible stderr line
  now, with PRD 00140 upgrading that to tool-native `console.warning`
  formatting, not introducing visibility from nothing.
- **Next likely changes this design should not box in:** (1) PRD 00140
  routing the warning through each tool's own `console.warning` instead of
  (or in addition to) the logger - this design's warning is a single
  `logger.warning(...)` call in one place, trivial to wrap or replace
  without touching the registry; (2) a future per-tool opt-out or stricter
  mode (warn -> fail for a specific shared key) - the validity test is two
  boolean expressions, easy to parameterize later; (3) a `buvis-gems
  doctor`/lint command that calls `known_tool_names()` directly to report
  the full registry for debugging - the function's pure, no-argument shape
  already supports that without change.
- **Scaffold drift window.** Until the `tools/lib/scaffold.py` follow-on
  above lands, every tool scaffolded after this PRD is, by construction, a
  "registry miss" for its own namespace section until a human remembers to
  add its entry-point line - the same failure mode as the first Risk
  bullet, just guaranteed rather than accidental for any new tool in the
  interim.
- **`lru_cache(maxsize=1)` is shared process-wide across the whole pytest
  session**, not scoped to this PRD's own tests - any earlier test that
  calls `ConfigResolver.resolve()` against a `config.yaml`/`buvis.yaml`
  before `uv sync` has refreshed `entry_points.txt` (the staleness risk
  below) would cache an empty frozenset for the rest of the process,
  silently weakening the check for every later test, not just this PRD's.
  Mitigation, not a design change: a `tests/lib/pybase/configuration/`
  `conftest.py` fixture that calls `known_tool_names.cache_clear()`
  (autouse, function-scoped, for this test module only - never global,
  since clearing it globally on every test in the suite would reintroduce
  the per-call metadata-scan cost this cache exists to avoid) rather than
  relying on each test author to remember; this is a task-level test
  concern, not a change to `registry.py` itself.
- **Editable-install metadata staleness.** `pyproject.toml`'s new
  entry-point group only takes effect in a dev checkout after `uv sync`
  regenerates the editable install's `entry_points.txt`; a stale `uv.lock`/
  venv from before this change would see an empty `buvis.config_settings`
  group (not a crash - `known_tool_names()` returns `frozenset()`, and the
  resolving tool's own `known_keys` is still checked independently). Task
  sequencing must run `uv sync` before any test that asserts a real
  cross-tool namespace section is recognized.

## Test strategy outline

- **Unit, `registry.py`:** call `known_tool_names.cache_clear()`, then
  monkeypatch `importlib.metadata.entry_points` to return a small fixture
  set of `EntryPoint`-shaped objects with distinct `.name` values (no real
  settings classes needed - `.load()` is never called) - assert
  `known_tool_names()` returns exactly that name set. Also assert a second
  call without re-monkeypatching returns the same (cached) result, and
  that `cache_clear()` followed by a new monkeypatch changes it - proves
  the cache is real and clearable.
- **Unit, `resolver.py` (the PRD's own evidence case, Success Metric 1):** a
  `config.yaml` containing `srouces: [x]` (the typo from the PRD) resolved
  for `BraidSettings` (which has a `sources` field, matching the PRD's own
  evidence), with `known_tool_names` monkeypatched to a fixed frozenset
  that does not contain `"srouces"` - assert `resolve()` returns
  **rc-equivalent success** (no exception) and a `logger.warning` call
  fires naming the file and `srouces` (via `caplog`). This is the
  regression test for the bug this PRD fixes - it must fail against the
  current code before the fix (today's code fully skips the check for
  `config.yaml`, so no warning fires either way; after the fix, the
  warning fires).
- **Unit, `resolver.py` (Success Metric 2a - a sibling tool's namespace
  section is not a false positive):** adapt
  `test_shared_config_keeps_other_tool_namespaces` from
  `tests/lib/pybase/configuration/test_tool_config_keys.py` (which already
  resolves `BraidSettings` against a `buvis.yaml` carrying `sysup: {...}`
  and `bim: {...}` sections) to also assert **no warning fires** (via
  `caplog`) for either section, with the real entry-point registry (no
  monkeypatching - `sysup`/`bim` are real registered tool names once
  `pyproject.toml` ships this PRD's entry-point group). This directly
  guards the distinction this PRD must get right: a typo warns, a real
  tool's namespace section does not.
- **Unit, `resolver.py` (Success Metric 2b - the resolving tool's own
  valid fields are not false positives):** a new sibling test, modeled on
  `test_known_directives_and_global_fields_remain_valid` but with the file
  named `config.yaml` instead of `candidate.yaml` (the existing test stays
  untouched - it covers the explicit/custom-filename path): own
  `sources+`/`policies` keys plus a bare `GlobalSettings` field like
  `debug`, resolved for `BraidSettings` - assert no warning, proving
  `known_keys` alone (unchanged, already inheriting global fields) covers
  the resolving tool's own valid keys without any registry involvement.
- **Unit, `resolver.py` (explicit/custom file unchanged):** the existing
  `test_rejects_unknown_tool_keys_before_projection`'s `"explicit"` case
  (`custom.yaml` + unknown key -> `ConfigurationError`, the PRD's own `rc
  2` evidence) continues to pass unmodified - confirm this change's diff
  does not touch the `elif known_keys is not None` branch's behavior.
- **Integration (real entry points, no monkeypatching):** after `uv sync`
  picks up the new `pyproject.toml` entry-point group, call
  `known_tool_names()` directly and assert it is a superset of
  `{"sysup", "backup", "braid", "bim"}` (or similar, a handful of real,
  always-present tool names) - proves the packaging wiring (not just the
  function logic) actually works end to end in this environment. Mark
  this test so a future reader knows it depends on editable-install
  metadata being current (a one-line comment, not a new marker - `pytest
  -m lib` already selects it by path).

## Review log

- non-blocking: the `GlobalSettings.model_fields` explicit union term was
  redundant (every `<Tool>Settings` already inherits global fields) -
  removed; `known_keys or set()` alone carries the current tool's globals.
- question: `bim/settings.py`'s "import-light" status is a snapshot fact,
  not an enforced invariant, so a future heavy import there would silently
  drop bim from the registry - recorded as an accepted Risk, not fixed now
  (no lint added at this PRD's scope).
- non-blocking: the `tools/lib/scaffold.py` follow-on leaves a drift window
  where every newly scaffolded tool is a registry miss until a human adds
  its entry-point line - recorded as an explicit Risk bullet.
dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 2, question 1
- non-blocking: the "bare log line until PRD 00140" framing was inaccurate -
  `logging.lastResort` already prints `logger.warning` to stderr with no
  handler configured; corrected the Risk bullet.
- question: `lru_cache(maxsize=1)` is shared across the whole pytest
  session, not just this PRD's tests - recorded as a Risk with a
  function-scoped `cache_clear()` fixture as the mitigation, not a code
  change.
dispatch 2: codex unavailable, Claude fallback
dispatch 2 (claude-fallback): cardinal-sin 0, blocker 1, non-blocker 2, question 1
- verification pass: both the lru_cache fix (dispatch 1) and the broad
  exception-handling fix (dispatch 2) confirmed sound against the doc and
  the live `resolver.py`/`settings.py`; zero new findings.
dispatch 3: codex unavailable, Claude fallback
dispatch 3 (claude-fallback): cardinal-sin 0, blocker 0, non-blocker 0, question 0

**Post-dispatch-3 correction (before hand-off to planning, not a new
reviewer dispatch):** re-reading `docs/source/configuration.rst` and
`tests/lib/pybase/configuration/test_tool_config_keys.py` while preparing
to hand off to `/autopilot:plan-tasks` surfaced that every dispatch above
reviewed a design built on a wrong premise: shared config files do **not**
merge other tools' *fields* flat at the top level - they carry a `<tool>:`
**namespace section** per tool, already documented
(`configuration.rst:118-122`) and already tested
(`test_shared_config_keeps_other_tool_namespaces`), which the resolving
tool's own resolve() simply ignores. The registry this design needs is the
set of **tool names**, not a union of every tool's **settings fields** -
`ep.load()` and all per-tool `model_fields`/`config_deferred_keys`
collection are unnecessary and have been removed; `known_tool_names()`
reads only `EntryPoint.name`, importing no tool code at all. This also
retires dispatch 1 and 2's blocking findings as moot by construction
(there is no `ep.load()` call left to be slow or to raise), not merely
fixed. Every section above (`Architecture fit`, `Interfaces & contracts`,
`Module placement`, `Data flow`, `Reuse inventory`, `Alternatives
considered`, `Risks & edge cases`, `Test strategy outline`) was rewritten
to the corrected scope before this doc was handed to planning; nothing
below this line was reviewed by an external dispatch, because the
correction came from reading the repository's own already-tested
contract, not from a new design decision warranting a fresh adversarial
pass.
