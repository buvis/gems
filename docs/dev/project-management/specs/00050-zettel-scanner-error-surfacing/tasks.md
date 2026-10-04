# zettel scanner: surface parse errors instead of dropping notes

<!-- tasks; migrated from PRD 00050 flat file -->

## Tasks

### Phase 0: Core
- [ ] Stop discarding `_errors`; warn-once via console and/or expose a structured errors field — Acceptance: a malformed note logs a warning naming the file; good notes still return.
- [ ] Wrap the Python fallback loop to collect per-file errors matching Rust semantics — Acceptance: parametrized test shows both backends report the bad file and return the rest.
