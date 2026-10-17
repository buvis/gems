# Discovery: dot pull secret divergence

## Classification

Depth: standard | Date: 2026-10-16

Source: `idea.md` beside this file. Follow-up to PRD 00095 (design review
disposition 2).

## Problem

00095 made `dot pull` save uncommitted edits that clash with incoming commits
to a patch before resetting them. git-secret plaintext is gitignored, and only
`<file>.secret` is tracked. `pull()` never runs `secret hide`, so a plaintext
edit never reaches the tracked `.secret`. The edit is missing from the
staged/unstaged lists, no patch is saved, and the final `cfg secret reveal -f`
overwrites it without a word. This bug predates 00095, but it is the same
data-loss class 00095 closed for normal files.

## Requirements

### Must have

- **M1 Hide before selection**: when git-secret is installed and an upstream
  exists, `DotGitService.pull` runs `cfg secret hide -m -F` after the upstream
  check and before `_select_divergent`. An edited plaintext becomes a dirty
  `<file>.secret` (plus a dirty `.gitsecret/paths/mapping.cfg`). The 00095
  selection, patch, reset and pull then handle it unchanged. The patch holds
  ciphertext only.
- **M2 Fail closed**: a hide error stops the pull before any diff, save, reset
  or `cfg pull`. Error: `secret hide failed: <err>`.
- **M3 No git-secret, no hide**: when git-secret is not installed, or no
  upstream exists, there is no hide call. Pull behaves exactly as under 00095.
  Without git-secret there is no reveal either, so nothing gets overwritten.
- **M4 Recovery hint**: after each completed reset of a selected path ending in
  `.secret`, add one warning:
  `secret <plain> saved encrypted in patch; to read it, git apply the patch at its base commit and run git secret reveal there`
  (`<plain>` is the path minus `.secret`). The 00095 lines (`divergence patch
  saved: ...`, `reset to HEAD, local edit in patch: ...`) stay byte for byte.
- **M5 Docs**: the `dot pull` divergence section in `docs/source/tools/dot.rst`
  and `README.md` covers secrets: the patch holds ciphertext, the recovery
  steps (worktree at base, `git apply`, `git secret reveal`, copy, remove the
  worktree), and that a `mapping.cfg` entry is git-secret hash bookkeeping that
  the next hide rewrites. `CHANGELOG.md` gets a `**dot**:` Fixed entry.

### Nice to have

- None. Skipping a patch that holds only `mapping.cfg` was considered and
  dropped: one uniform rule beats a special case.

### Out of scope

- `pull.rebase=true` behavior and concurrent same-second pulls (00095 design notes).
- Adding `-F` to `status()`/`commit()` hide calls (`_hide_secrets`). They hit
  the same missing-plaintext abort, but no data is lost there.
- Installing git-secret in CI (Q1).
- Saving plaintext bytes outside git (rejected, see Approach).

## Constraints

- Lands after 00095. On 2026-10-16, 00095 is done on the pushed branch
  `feature/00095-dot-pull-divergence-report` and not merged to `master`; this
  branch is cut from `master` and has none of its code.
- No new dependencies. Output goes through `CommandResult.warnings`.
- `hide` encrypts to the public keys in `.gitsecret/keys`, so it needs no
  passphrase. The passphrase stays a reveal-only argument.

## Codebase Context

- **Relevant code** (00095 branch): `src/tools/dot/git/service.py`
  `DotGitService.pull` (fetch, `has_upstream`, `_save_and_reset_divergence`,
  pull/submodule steps, `cfg secret reveal -f`); `_select_divergent` (four NUL
  lists); `_hide_secrets` (`cfg secret hide -m`, used by `status`, `commit`,
  `has_uncommitted_changes`).
- **Conventions**: git through the `cfg` alias and `ShellAdapter.exe`, which
  returns `(err, out)` and sets `err` only on a non-zero exit. The `-F` warning
  on stderr with exit 0 is not an error. Messages are lowercase,
  `<what> failed: <err>`.
- **Integration points**: `pull()` only. `CommandPull` and the TUI already pass
  the service result's warnings through (00095).
- **Tests**: `tests/tools/dot/test_pull_divergence.py` (`Harness`, command
  constants, ordered `events`); `tests/tools/dot/conftest.py` (`_git`, `_run`,
  `_setup_bare_host`, `two_host_setup`, `_disable_git_secret`).
  `test_git_service.py` `TestDotGitServicePull` stubs `has_upstream` to
  `False`, so hide (gated on upstream) leaves its sequences unchanged. No
  existing test runs real git-secret.

## Approach

- **Chosen**: ciphertext through hide (M1). Probed with git-secret 0.5.0 and
  gpg in a throwaway repo. `hide -m` after a plaintext edit dirties
  `s.txt.secret` and `mapping.cfg` and leaves unedited secrets clean. Saving
  them with `git diff --binary --full-index HEAD`, resetting, `reveal -f`
  brings back the old plaintext. Then `worktree add <dir> <base>` +
  `git apply` + `git secret reveal` in that worktree brings back the edited
  plaintext.
- **Why**: no plaintext outside git. It reuses 00095's selection, save and
  reset with no new path. It needs one shell call.
- **Rejected**: save plaintext bytes into the divergence dir. Secrets would sit
  in cleartext outside git (0o700 does not change that). It also needs a new
  "was the plaintext edited" check (decrypt `HEAD`, or compare
  `mapping.cfg` hashes) and a second save format.
- **Why `-F`**: probed. Plain `hide -m` exits 1 with
  `abort: file not found` when any registered plaintext is missing (e.g. a
  reveal that never ran), after encrypting earlier files. Under M2 that blocks
  every pull on such a host. `-F` skips the missing file with a warning and
  exits 0. A missing plaintext holds no edit, so skipping it loses nothing.

## Success Criteria

- Mocked: git-secret installed + upstream -> command order is `UPSTREAM`,
  `cfg secret hide -m -F`, then the four diff lists. Hide error -> failure
  `secret hide failed: <err>`, no diff, no capture, no restore, no `cfg pull`.
  No git-secret, or no upstream -> no hide command. Selected
  `.gitsecret/paths/mapping.cfg` + `x.secret` -> 00095 lines plus one hint for
  `x` only. A failed reset of `x.secret` -> no hint for `x`.
- Real git (skipped when `git-secret` or `gpg` is missing): A edits and hides
  secret `s`, pushes. B edits `s`'s plaintext uncommitted. B `dot pull`
  succeeds, B's `s` holds A's plaintext, the patch names `s.secret`, and
  applying it in a worktree at its base then `git secret reveal` gives B's
  edit byte for byte. B's edit to a second secret `k` that upstream left alone
  survives the pull. With `k`'s plaintext missing on B, the pull still
  succeeds (`-F`).
- Existing `test_pull_divergence.py`, `test_git_service.py`,
  `test_pull_divergence_two_hosts.py` pass unchanged.

## Risks

- **Side effect: hide dirties more than the clash**: every locally edited
  secret gets fresh ciphertext. That is the same state `dot status` already
  leaves. The non-clashing ones stay dirty (not reset), and the final
  `reveal -f` decrypts them back to the user's own bytes.
- **`mapping.cfg` churn**: if any local secret is edited and upstream changed
  any secret, `mapping.cfg` is selected, saved and reset. It holds only hashes,
  and the next hide rewrites the local entries. Docs say so.
- **Pull stops after hide ran**: on a mixed-state or save failure, the
  `.secret` files stay re-encrypted (dirty), the same as after `dot status`. No
  plaintext is touched.
- **Repo with git-secret installed but no `.gitsecret`**: hide fails, so pull
  now stops before merging. Today it merges, then fails at reveal (probed:
  both abort). That only happens on a misconfigured host. The error names the
  hide step, and `dot run pull` stays as the manual way out.
- **gpg socket path limit on macOS**: `git secret tell` fails under pytest's
  long `tmp_path` (probed). The real-git test builds its repos under a short
  `tempfile.mkdtemp(dir="/tmp")` and kills `gpg-agent` for each homedir in
  teardown.

## Open Questions

- None. Q1 settled CI coverage. The rest was settled by the code and probes
  (see the Discovery Log).

## Discovery Log

### Q1: The real git-secret test runs on dev machines but neither CI runner has git-secret. How should CI treat it?
**Answer**: Skip when missing. `skipif` git-secret or gpg is absent; CI
skips it and the mocked tests guard the call order. Known gap: CI never runs
real hide/reveal.

### Inferred (not asked)
- Mechanism (idea decision 1): ciphertext through hide. Plaintext outside git
  has no upside the probe did not already deliver.
- Hide failure (idea decision 2): stop before any reset, as the idea itself
  requires. `-F` comes from the missing-plaintext probe. No hide without
  git-secret (and then no reveal either), and none without an upstream (no
  selection runs).
- Hide placement: inside the `has_upstream()` branch. Without an upstream there
  is nothing to select, and `TestDotGitServicePull` sequences stay unchanged.
- Recovery wording (idea decision 3): keep the 00095 lines and add one hint per
  reset `.secret` path. Steps go in docs, not in the message.
- Tests (idea decision 4): mocked cases in the `Harness` style, plus a real
  two-host file with its own short-path fixture (pytest `tmp_path` breaks gpg
  on macOS).
