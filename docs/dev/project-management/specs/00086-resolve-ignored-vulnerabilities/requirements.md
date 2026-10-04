# deps: resolve every pip-audit-ignored vulnerability and stop suppressing new ones

<!-- requirements; migrated from PRD 00086 flat file -->

## Problem

The repository's security posture has quietly become **suppress-and-forget**.
The CI `lint` job audits dependencies with:

```yaml
# .github/workflows/test.yml, line 95 (the `lint` job)
run: uv run pip-audit --skip-editable --ignore-vuln CVE-2026-4539  # pygments, no fix available yet
```

Two failures are hiding behind this one line, verified against the tree on
2026-09-30:

1. **A STALE suppression.** `CVE-2026-4539` (pygments ReDoS) is **fixed in
   pygments 2.20**, and `uv.lock` already resolves **pygments 2.21.0**
   (`uv.lock` line 2216). The vulnerable code is not installed — the
   `--ignore-vuln` entry and its "no fix available yet" comment are **dead** and
   have been masking the audit for no reason. There is nothing to accept here;
   the ignore should simply be removed.

2. **A NEW unhandled CVE that is currently red on every PR.** `pip-audit` now
   flags **`oauthlib 3.3.1` / `CVE-2026-49265`** (fix in **4.0.0**). oauthlib is
   a **transitive** dependency: `oauthlib` ← `requests-oauthlib 2.0.0` ←
   `jira 3.10.5` (the bim tool's Jira adapter). It is on **master**, so the
   `lint` job — and the aggregation `test` gate that depends on it — is failing
   on master and on every open PR (this is what blocked PR #196). The last time
   this class of failure appeared, the tempting fix was to add another
   `--ignore-vuln`; that would grow exactly the suppress-and-forget list this
   PRD exists to eliminate.

The root cause is not either individual CVE — it is that the audit has **no
mechanism to retire a suppression once its fix ships**, so a temporary ignore
becomes permanent, silently masks the dependency it named, and normalizes adding
the next one. The user's directive is explicit: **we do not tolerate ignoring
vulnerabilities.** This PRD resolves the two live findings by *fixing* them, not
suppressing them, and closes the process gap that let a suppression go stale.

### Verified facts

- `.github/workflows/test.yml:95` — the sole `pip-audit` invocation, in the
  `lint` job, carrying `--ignore-vuln CVE-2026-4539`.
- `uv.lock:2216` — `pygments` resolves to `2.21.0` (> 2.20, the CVE-2026-4539
  fix). The suppression is therefore a no-op that masks nothing real but hides
  the audit surface.
- `uv.lock:1711` — `oauthlib` resolves to `3.3.1`; `uv.lock:2416` —
  `requests-oauthlib 2.0.0` depends on `oauthlib`; `uv.lock` jira block depends
  on `requests-oauthlib`. Neither `pyproject.toml` nor `uv.lock` pins oauthlib
  directly — it is purely transitive.
- oauthlib **4.0.0** (released 2026-09-28) fixes `CVE-2026-49265` and contains
  **2 breaking changes**, both in the OAuth2 **provider** surface: JSONP removed
  from the token-revocation endpoint, and client-authentication validation
  reordered across grants. gems consumes oauthlib only as an OAuth1/OAuth2
  **client** via `jira` — it implements no provider endpoints — so the breaks are
  expected to be irrelevant, but this must be confirmed, not assumed.

## Solution

Fix both findings at the dependency layer, remove the stale ignore, and make the
audit self-policing so no future suppression can silently outlive its fix.

1. **Drop the stale pygments ignore.** Remove `--ignore-vuln CVE-2026-4539` from
   the `lint` step. `pygments 2.21.0` is already resolved, so the audit passes
   that CVE on its own. No version change needed.

2. **Resolve the oauthlib CVE by upgrading, not ignoring.** Raise the resolved
   `oauthlib` to `>= 4.0.0`. Because it is transitive, prefer the least-invasive
   mechanism that pins the *resolution* without over-constraining:
   - First choice: a **constraint** that lifts the floor (a
     `[tool.uv] constraint-dependencies` / equivalent entry, or a direct
     `oauthlib>=4.0.0` dev/runtime constraint) so `uv lock` resolves 4.0.0,
     leaving `requests-oauthlib`/`jira` to pull it.
   - Regenerate `uv.lock` and confirm `oauthlib` is `>= 4.0.0` and
     `requests-oauthlib` still resolves against it.
   - **Verify the breaking changes do not touch gems.** The two 4.0.0 breaks are
     provider-side; gems uses the Jira *client* path. Confirm by (a) grepping the
     codebase for any direct `oauthlib` import (expected: none) and (b) running
     the bim Jira-adapter tests green against the upgraded lock. If a real break
     surfaces, it escalates to its own decision — do **not** paper over it with an
     ignore.

3. **Make suppressions self-expiring, so this cannot recur.** Any `--ignore-vuln`
   that ever remains legitimate (a CVE with genuinely no upstream fix) must not
   be allowed to go stale. Add a lightweight guard so a suppression is
   re-justified every run:
   - Move the ignore list out of the inline shell flag into a small, commented
     **audit config** (e.g. a `pip-audit`-read file or a documented wrapper) where
     each entry records the CVE, the package, *why* it is unfixable, and the date
     added.
   - Add a check (a dev script run in the same `lint` job, or a scheduled cron)
     that fails — or at minimum warns loudly — when an ignored CVE now has a fix
     available in the resolved tree, so a stale entry like CVE-2026-4539 is caught
     the moment its fix ships rather than masking the audit indefinitely.
   - Net intent: the steady state is **zero** ignores; any non-empty list is
     visible, dated, justified, and actively re-checked.

## Requirements

### Must have

- `pip-audit` in CI runs with **no stale ignore**: `CVE-2026-4539` is removed
  from the `lint` step (its fix is already resolved).
- `oauthlib` resolves to **`>= 4.0.0`** in `uv.lock`, clearing `CVE-2026-49265`,
  with `requests-oauthlib`/`jira` still resolving correctly.
- The bim Jira integration is verified to still work against the upgraded
  oauthlib (no direct oauthlib import in gems; bim Jira-adapter tests green).
- After the change, `uv run pip-audit --skip-editable` (no `--ignore-vuln`)
  passes on the resolved tree, or — if any *genuinely unfixable* CVE remains —
  its ignore lives in the new dated/justified config, not an anonymous inline
  flag.
- CHANGELOG updated under `[Unreleased]` (a `deps`/security bullet) in the same
  commit, per the blocking CHANGELOG rule.

### Nice to have

- A scheduled (weekly) `pip-audit` run that reports newly-published CVEs against
  the current lock, so a fresh CVE is seen on a schedule rather than only when it
  reddens an unrelated PR.
- The stale-suppression check wired as a hard `lint` failure (not just a warning)
  once the config format is in place.

### Out of scope

- Bumping any dependency **not** implicated by a current CVE. This is a
  security-remediation PRD, not a general dependency-refresh.
- Reworking the OAuth/Jira integration's behaviour — only the resolved oauthlib
  version changes; gems' own auth code is untouched (and expected to be
  break-free since it is client-side).
- The unrelated `_BRUSH_CADENCE_DAYS`-unused finding (its own follow-up).

## Success Criteria

- CI `lint` runs `pip-audit` with **zero** anonymous inline ignores; the audit is
  green because the vulnerable versions are actually gone, not hidden.
- `oauthlib >= 4.0.0` is resolved (CVE-2026-49265 cleared) and the bim Jira
  integration still works.
- The stale pygments ignore is gone.
- Any future suppression is dated, justified, and automatically re-checked — a
  fixed CVE can no longer sit ignored, so PR #196's class of block (a fresh CVE
  on an unrelated branch) is resolved at the dependency layer, never by adding to
  a suppress-and-forget list.
