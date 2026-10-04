# pybase config: directive-tagged list merge (append / remove)

<!-- design; migrated from PRD 00080 flat file -->

## Implementation

### Module: pybase.configuration.loader
- **Location**: `src/lib/buvis/pybase/configuration/loader.py`
- **Responsibility**: `_deep_merge` gains directive parsing (`key+` / `key-`),
  list append-dedup / remove, non-list-base error, and directive stripping.
  `merge_configs` gains the optional `known_keys` typo-guard parameter.
- **Constraint**: this function underpins the entire config stack and
  `ConfigResolver` (just stabilized by 00081). Change is additive and gated on the
  suffix, so the plain-key path is byte-for-byte unchanged.

### Tests
- **Location**: mirror under `tests/lib/pybase/` alongside the existing loader /
  resolver tests.
- Cover: append-dedup, remove-absent-noop, same-layer +then-, plain-key reset,
  non-list-base error, three-layer accumulation in ranked order, and a regression
  fixture proving plain lists still replace.

### Dependencies
- None new. Pure standard library + existing loader.

## Provenance

Requirements elicited in a dashboard session on 2026-09-26 while eliciting the
backup tool PRD (00082). The user asked whether the core config module could make
appends easier; inspection of `_deep_merge` confirmed lists replace wholesale with
no append path. The user chose **Option A: directive-tagged merge (`key+` /
`key-`)** over a union-by-configured-key variant and over solving append per-tool,
because append/remove is a recurring need (sysup 00079 already worked around
list-replace with a keyed map; backup 00082 needs additive excludes) and putting
the directive in the data keeps the intent visible with no per-tool code. sysup's
in-progress implementation revisits its workaround once this lands. Grounded
against `loader.py` `_deep_merge` / `merge_configs` and PRD 00081 (config
precedence fix) as they stood on that date.
