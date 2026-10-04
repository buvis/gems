# Prune the formatting package and relocate suggest_tags

<!-- design; migrated from PRD 00061 flat file -->

## Implementation

### Module: pybase.formatting (prune) + bim (gain suggest_tags)
- **Location**: `src/lib/buvis/pybase/formatting/string_operator/`, `src/tools/bim/shared/`
- **Responsibility**: formatting keeps only its live, pure helpers; bim owns its Ollama tag-suggestion.
- **Exports**: trimmed `StringOperator`; a small `suggest_tags` adapter in bim

### Dependencies
- No dependency. (Do after 00050/00061-adjacent zettel work only if convenient; not required.)
