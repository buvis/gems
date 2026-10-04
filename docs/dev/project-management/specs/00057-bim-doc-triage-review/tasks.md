# bim doc triage: list-and-approve review surface

<!-- tasks; migrated from PRD 00057 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] `CommandTriageList` enumerating `<business_root>/_triage/*.proposed.yml` proposals (no deps) — Acceptance: list matches the triage dir in a fixture (issuer, doc type, date, `triage_reasons`, path).

### Phase 1: Core
- [ ] `CommandTriageApprove` sets approved + promotes via the collision-safe path (depends on: Phase 0) — Acceptance: fixture proposal approved and filed; no YAML hand-edit needed.
- [ ] Register both in the serve action registry per `dev/local/specs/all-interface-architecture.md`; update the `bim.rst` triage docs (depends on: the seam spec) — Acceptance: `triage_list`/`triage_approve` are invocable through the generic actions route (TestClient test); docs describe the new flow.
