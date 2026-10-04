# pybase config: fix inverted precedence in the config resolver

<!-- requirements; migrated from PRD 00081 flat file -->

## Problem

`ConfigResolver` inverts config-file precedence for **every** buvis tool. The
resolver reverses `find_config_files()` and feeds the result to `merge_configs`
(later wins), on the assumption that `find_config_files` returns a clean
highest-to-lowest ranking:

```python
# src/lib/buvis/pybase/configuration/resolver.py:186-188
discovered_files = self.loader.find_config_files(tool_name, config_dir=config_dir)
loaded_configs = [self.loader.load_yaml(path) for path in reversed(discovered_files)]
return self.loader.merge_configs(*loaded_configs) if loaded_configs else {}
```

But `find_config_files` does **not** return a single ranking. It returns
`_get_candidate_files`'s output unchanged, which iterates
`for base in dirs: [config.yaml, buvis.yaml, buvis-{tool}.yaml]` where `dirs` is
**highest-priority-first** (`$BUVIS_CONFIG_DIR` → `~/.config/buvis` → cwd) but the
stems within each directory are appended **lowest-first**
(`config` < `buvis` < `buvis-{tool}`). The list is therefore mixed-order — dirs
descending, stems ascending. A blind `reversed()` inverts precedence in two ways:

1. **Across directories:** `~/.config/buvis` ends up beating `$BUVIS_CONFIG_DIR`.
2. **Within a directory:** the generic `config.yaml` beats the tool-specific
   `buvis-{tool}.yaml`.

(2) is the opposite of the obviously-intended behavior: a tool-specific file
should override the generic one, not the reverse.

### Confirmed empirically

With `$BUVIS_CONFIG_DIR` set and both `config.yaml` (`k: hi_config`) and
`buvis-sysup.yaml` (`k: hi_buvis_sysup`) present in it:

```
find_config_files order:  [hi/config.yaml, hi/buvis-sysup.yaml]   # stems ascending
reversed()+merge winner:  k = "hi_config"          # WRONG
intended winner:          k = "hi_buvis_sysup"      # tool-specific should win
```

Root cause is a docstring that lied: `find_config_files` claimed "ordered from
highest to lowest priority" while returning mixed order. The docstring has been
corrected (comment-only change, `loader.py`) to describe the real mixed order and
warn callers not to `reversed()` it; **this PRD fixes the actual resolver logic.**

### Blast radius

Every tool that resolves settings through `buvis_options` / `get_settings` →
`ConfigResolver`. Any machine that has BOTH a generic (`config.yaml`/`buvis.yaml`)
and a tool-specific (`buvis-{tool}.yaml`) file setting the same key currently gets
the generic value, not the tool-specific one. Machines with only one file per key
are unaffected (nothing to invert), which is likely why this went unnoticed.

## Solution

Replace the `reversed()` in `ConfigResolver._load_yaml_from_discovery` (the method
at `resolver.py:~186`) with an explicit sort of the discovered files by
`(directory_rank, stem_rank)` ascending (lowest priority first), then
`merge_configs` in that order so higher-priority layers win. Directory rank
follows `get_config_dirs()` (with cwd lowest); stem rank is
`config < buvis < buvis-{tool}`.

Preferred implementation: add a small helper to `ConfigurationLoader` that returns
the discovered files **already sorted low-to-high** (e.g.
`find_config_files_ranked()`), so the ordering contract lives in one place next to
the code that knows the ranks, and the resolver just does
`merge_configs(*[load_yaml(f) for f in ranked])` with no `reversed()`. This also
gives PRD 00079's `sysup.config.load_config` a correct primitive to reuse instead
of re-deriving the sort.

## Requirements

### Must have

- Config precedence is correct: within a directory, `buvis-{tool}.yaml` overrides
  `buvis.yaml` overrides `config.yaml`; across directories, `$BUVIS_CONFIG_DIR`
  overrides `~/.config/buvis` overrides cwd. Verified by test with the empirical
  case above.
- No `reversed(find_config_files(...))` remains in the resolver.
- Existing single-file-per-key setups are unchanged (regression guard).

### Nice to have

- Expose the ranked-order helper on `ConfigurationLoader` so PRD 00079 and any
  future caller reuse it instead of re-implementing the sort.

## Success Criteria

- Tool-specific config reliably overrides generic config; `$BUVIS_CONFIG_DIR`
  reliably overrides the default dir. Full suite green.
