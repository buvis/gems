# Prune the formatting package and relocate suggest_tags

<!-- requirements; migrated from PRD 00061 flat file -->

## Problem

The `formatting` package is a 642-LOC bottom-layer library with only **4 production callers total**, one each: `camelize` (`zettel_factory.py:37`), `as_note_field_name` (file-parser helpers), `replace_abbreviations` (`fix_title_format.py:29`), and `suggest_tags` (`bim/shared/import_helpers.py:102`). Everything else — `slugify`, `prepend`, all of `word_level_tools.py`, `humanize`, `as_graphql_field_name` — has zero production callers and is kept alive only by ~50 test references. Worse, `suggest_tags` is an **Ollama HTTP client** (`formatting/string_operator/suggest_tags.py`, urllib + a `console` import) living in a pure string-formatting package — an external-service integration in the wrong layer, with exactly one consumer (bim). The dead `formatting.slugify` is also one of three divergent slugify implementations in the repo.

## Solution

Delete the dead formatting surface down to the four live methods (and their tests). Relocate the `suggest_tags` Ollama client out of `formatting` into bim (its only consumer) as a small adapter, fixing the layering.

## Requirements

### Must have
- Remove the unused formatting methods (`slugify`, `prepend`, `word_level_tools.*`, `humanize`, `as_graphql_field_name`) and their now-orphaned tests; keep `camelize`, `underscore`/`as_note_field_name`, `replace_abbreviations`, and whatever the four live callers need.
- Move `suggest_tags` from `formatting/string_operator/` into bim (e.g. `bim/shared/`), drop the `string_operator` facade method that exposed it; update its single consumer's import.
- `formatting` no longer imports `console` or `urllib` (the external-service concern is gone from the bottom layer).
- `mypy` + `pytest` green; the four live callers unaffected.

### Nice to have
- Note in the roadmap's opportunistic list that `formatting.slugify` being gone leaves bim doc's `naming.py` and fren's python-slugify as the two intentional, distinct slug implementations (no further consolidation needed).

## Success Criteria

- ~400+ LOC of dead formatting surface removed; the package is pure again.
- The Ollama client lives with its consumer; layering restored.
