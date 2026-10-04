# deps: resolve every pip-audit-ignored vulnerability and stop suppressing new ones

<!-- design; migrated from PRD 00086 flat file -->

## Implementation

### CI: .github/workflows/test.yml
- **`lint` job, line ~95** — remove `--ignore-vuln CVE-2026-4539`. If the
  self-expiring-config approach lands, replace the inline flag with the
  config-driven invocation instead.

### Dependencies: pyproject.toml / uv.lock
- Add the minimal constraint that lifts `oauthlib` to `>= 4.0.0` (transitive
  floor), then `uv lock` to regenerate. Confirm the resolved `oauthlib` and that
  `requests-oauthlib`/`jira` still resolve. Do not add oauthlib as a direct
  runtime dependency of any tool — it stays transitive, only floored.

### Guard: dev/bin/ (or the lint step)
- A small script that reads the audit-ignore config and, for each entry, checks
  whether the resolved tree now satisfies a fixed version — failing/warning when
  a suppression is stale. Run it in the `lint` job. Keep it deterministic (code,
  not an LLM step), per the routing lesson.

### Tests
- **Location**: `tests/` mirror as applicable; the guard script gets a unit test
  under `tests/` (e.g. a fixture ignore-config with one stale + one live entry,
  asserting the stale one is flagged).
- Cover: the guard flags a stale suppression and passes a genuinely-unfixable
  one; the oauthlib upgrade leaves the Jira adapter tests green.

## Provenance

Directed by Tomáš on 2026-09-30: *"We can't tolerate ignoring vulnerabilities.
Please write PRD to solve all ignored vulnerabilities, including this new one."*
Prompted by PR #196 (postup 00085), whose `lint`/`test` gates were red on
`oauthlib 3.3.1` / CVE-2026-49265 — a pre-existing, freshly-published transitive
CVE unrelated to that branch. Investigation of the sole `pip-audit` invocation
(`.github/workflows/test.yml:95`) found the existing `--ignore-vuln
CVE-2026-4539` had already gone **stale** (pygments 2.21.0 in `uv.lock:2216`
already carries the fix), confirming the suppress-and-forget failure mode this
PRD closes. oauthlib 4.0.0 (2026-09-28) fixes the CVE; its two breaking changes
are OAuth2 provider-side, while gems uses oauthlib only as a Jira client via
`jira` → `requests-oauthlib`, so the upgrade is expected to be transparent —
to be verified, not assumed.
