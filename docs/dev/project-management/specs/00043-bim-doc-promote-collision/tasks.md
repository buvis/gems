# bim doc promote: stop overwriting on canonical-name collision

<!-- tasks; migrated from PRD 00043 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] Locate/extract the ingest collision resolver so promote can call it — Acceptance: one function resolves a base zk timestamp + canonical name to the first free path under an issuer dir, with the existing attempt cap.

### Phase 1: Core
- [ ] Call the resolver in promote before `source_pdf.replace` and the zettel write; fail loud on exhaustion (depends on: Phase 0) — Acceptance: regression test proves two same-name promotes both survive; exhaustion returns `success=False`, no file removed.
