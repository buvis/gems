# pybase config: directive-tagged list merge (append / remove)

<!-- requirements; migrated from PRD 00080 flat file -->

## Problem

The buvis config stack composes layers with `ConfigurationLoader.merge_configs`,
which calls `_deep_merge` (`src/lib/buvis/pybase/configuration/loader.py`). That
function has exactly two branches:

```python
def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for k, v in source.items():
        if k in target and isinstance(target[k], dict) and isinstance(v, dict):
            _deep_merge(target[k], v)   # dict-into-dict recurses
        else:
            target[k] = v               # everything else REPLACES
```

Dicts merge recursively; **every non-dict value — including every list —
replaces wholesale.** There is no way for a higher-priority layer to *add to* or
*remove from* a list a lower layer defined. A machine-local file that wants to
add one entry to a shared list must re-list the entire thing.

This is a recurring pain, not a one-off:

- PRD 00079 (sysup) hit it head-on: to let a machine add/override one updater
  without "list-append gymnastics", it modelled the updater set as a **flat keyed
  map** (`commands: {name: {...}}`) specifically so the loader's dict deep-merge
  unions by key. That works, but it forces a map shape on data that is naturally
  a list, purely to dodge list-replace.
- PRD 00082 (backup tool) needs exactly this for its exclude patterns: gem ships
  defaults, a user-wide file *adds* patterns, a machine-local file *adds or
  cancels* patterns. A plain `excludes:` list cannot express that under the
  current merge — each layer would clobber the last.

Any future list-valued setting that wants a shared base plus per-machine deltas
will hit the same wall.

## Solution

Teach `_deep_merge` a small, **opt-in, data-level directive grammar** on keys: a
trailing `+` means *append to* the same key's list, a trailing `-` means *remove
from* it. A plain key (no suffix) keeps today's replace semantics exactly, so
nothing that exists today changes behaviour.

```yaml
# layer 1 (gem default)
excludes: [node_modules, __pycache__, .venv]

# layer 2 (user-wide, higher priority) — ADD, don't replace
excludes+: [.terraform, .gradle]

# layer 3 (machine-local, higher priority still) — ADD one, CANCEL one default
excludes+: [.cache]
excludes-: [.venv]
```

Resolved `excludes`:
`[node_modules, __pycache__, .terraform, .gradle, .cache]` — order-preserving,
`.venv` cancelled, duplicates collapsed.

### Merge rules

- **`key`** (plain) — replace. Unchanged from today. A plain `key` in a later
  layer resets the accumulated list (append/remove history discarded), giving an
  explicit "start over from here" escape hatch.
- **`key+`** — the value (a list) is appended to the current `key` list,
  preserving order and skipping items already present (dedup). If `key` does not
  yet exist, `key+` seeds it.
- **`key-`** — each item in the value (a list) is removed from the current `key`
  list if present; absent items are a silent no-op.
- Within one layer, apply `+` then `-` (a layer that both adds and removes the
  same token nets to removed — removal wins, so a machine can hard-cancel).
- Directives apply to **list-valued** keys only. `key+` / `key-` whose base value
  is a non-list (scalar, dict) is a **merge error** surfaced through the loader,
  not a silent coercion.
- The directive is stripped before the merged dict is returned: consumers and
  Pydantic models see plain `excludes`, never `excludes+`. Models stay unchanged.

### Typo guard

A bare `+`/`-` suffix is easy to fat-finger (`exclude+` vs `excludes+`). Because a
directive on a key with no plain base just seeds a new list, a typo would
silently create `exclude` instead of extending `excludes`. Mitigation: the merge
records which base keys a `+`/`-` directive targeted; the loader can optionally be
given the set of known keys (from the caller's Pydantic model field names) and
warn — through `console` / logging — when a directive targets a key absent from
that set. This stays opt-in so the low-level `_deep_merge` needs no schema
knowledge; `merge_configs` gains an optional `known_keys` parameter.

## Requirements

### Must have

- `_deep_merge` recognizes `key+` (append, order-preserving, dedup) and `key-`
  (remove) directives on list-valued keys, across the whole config stack, for
  every tool — no per-tool code.
- Plain keys retain replace semantics identically to today (regression guard):
  every existing config resolves to the same value it does now.
- Directives are stripped from the merged output; downstream Pydantic models
  (`SysupConfig`, `SysupSettings`, all tool settings with `extra="forbid"`) see
  only plain keys and require no change.
- Within a layer, `+` then `-` ordering (removal wins over a same-layer add).
- A `+`/`-` directive whose base key is a non-list is a clear merge error routed
  through the loader's existing error path, never a stack trace or silent coerce.
- Correct interaction with 00081's now-fixed precedence: directives accumulate in
  the loader's low-to-high order (`find_config_files_ranked`), so a
  higher-priority layer's `+`/`-` sees the lower layers already folded in.

### Nice to have

- `merge_configs(*layers, known_keys=...)` optional typo guard that warns when a
  directive targets an unknown key.
- Document the grammar in the config docs (schema page) with the excludes example.

### Out of scope (v1)

- Directives on dict or scalar values (only list append/remove).
- Positional insert (append-only; no "insert before X").
- A `!clear` / replace-and-restart directive beyond the plain-key reset already
  described.
- Migrating sysup's keyed map back to a list — tracked as a follow-up (below),
  not required here.

## Success Criteria

- A shared list in a low-priority config plus `key+` / `key-` in higher layers
  produces the union-minus-removals with no per-tool code and no list re-listing.
- Every existing config resolves identically (plain keys unchanged); full suite
  green including the 00081 precedence tests.
- PRD 00082 (backup) can model `excludes` as a plain list and rely on this merge
  for user-wide / machine-local additive layering.
