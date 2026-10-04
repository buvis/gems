# dot rm: untrack (not destroy) secrets, and quote the filename

<!-- tasks; migrated from PRD 00045 flat file -->

## Tasks

### Phase 0: Core
- [ ] Change `_remove_encrypted` to untrack-without-delete (drop `-c`, keep plaintext) — Acceptance: regression test proves the plaintext survives an encrypted `dot rm`.
- [ ] `shlex.quote(self.file_path)` in `_remove_normal` (`:38`) and `_remove_encrypted` (`:46`) — Acceptance: test with a space/`;` filename shows the exact file acted on, no injection.
