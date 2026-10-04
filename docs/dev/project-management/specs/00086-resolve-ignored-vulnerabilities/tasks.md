# deps: resolve every pip-audit-ignored vulnerability and stop suppressing new ones

<!-- tasks; migrated from PRD 00086 flat file -->

## Tasks

### Phase 0: resolve the two live findings
- [ ] Remove the stale `CVE-2026-4539` ignore from the `lint` step —
      Acceptance: `uv run pip-audit --skip-editable` (no ignore) passes that CVE
      against `pygments 2.21.0`.
- [ ] Floor `oauthlib >= 4.0.0`, regenerate `uv.lock` — Acceptance: `uv.lock`
      shows `oauthlib >= 4.0.0`; `pip-audit` no longer reports CVE-2026-49265.
- [ ] Verify no gems break from oauthlib 4.0.0 — Acceptance: no direct
      `oauthlib` import in `src/`; bim Jira-adapter tests green against the new
      lock.

### Phase 1: prevent recurrence
- [ ] Move any remaining ignore into a dated/justified audit config; add the
      stale-suppression guard to the `lint` job with a unit test — Acceptance:
      the guard fails CI on a fixture stale entry and passes a live one.
- [ ] (nice-to-have) weekly scheduled `pip-audit` report.
