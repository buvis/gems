---
default_model: opus
model_tier_rationale: destructive blast radius - adds a step to the pull path that resets user edits in $HOME; must fail closed before any reset
---

# dot pull: save divergent secret plaintext

Source: `docs/dev/project-management/intake/processed/00097-dot-pull-secret-divergence/discovery.md`
(M1-M5, Q1). Follow-up to PRD 00095 (design review disposition 2 in
`docs/dev/project-management/designs/00095-dot-pull-divergence-report-v1-design.md`).

## Overview

### Problem Statement
00095 made `dot pull` save uncommitted edits that clash with incoming commits
to a patch, then reset them to `HEAD`. git-secret plaintext is gitignored;
only `<file>.secret` is tracked. `DotGitService.pull` never runs
`secret hide`, so a plaintext edit never reaches its `.secret`. The edit
is missing from the staged/unstaged lists, nothing saves it, and the
final `cfg secret reveal -f` overwrites it without a word. After this PRD,
pull hides first. The edited `.secret` then joins the 00095 selection and is
saved as ciphertext before upstream wins.

### Target Users
The solo dotfiles owner who edits git-secret files in place on several hosts.

### Success Metrics
- `tests/tools/dot/test_pull_divergence.py` (new class `TestSecretHide`) and
  `tests/tools/dot/test_pull_secret_divergence_two_hosts.py` pass. The
  real-git file runs wherever `git-secret` and `gpg` are on `PATH`. CI has
  neither, so CI skips it (accepted gap, discovery Q1).
- Two-host case: B edits secret `s.txt` uncommitted. A changes `s.txt` and
  pushes. B pulls, and `s.txt` holds A's plaintext. The patch holds no B
  plaintext. Applying it in a clone at its base commit, then
  `git secret reveal -f`, gives B's edit byte for byte.
- With git-secret absent, or with no upstream, the pull command sequence is
  unchanged from 00095.

## Functional Decomposition

### Capability: Secret divergence save
Bring edited secret plaintext into the 00095 divergence flow as ciphertext.

#### Feature: Hide before selection
- **Description**: Re-encrypt edited secrets so their `.secret` files show as dirty before divergence selection.
- **Inputs**: fetched repo with an upstream; git-secret on `PATH`.
- **Outputs**: dirty `<file>.secret` and `.gitsecret/paths/mapping.cfg` for each locally edited secret, or a failure.
- **Behavior**: in `DotGitService.pull`, inside the `if self.has_upstream():`
  branch and before `self._save_and_reset_divergence(exclude)`:
  ```python
  if self.shell.is_command_available("git-secret"):
      err, _out = self.shell.exe("cfg secret hide -m -F", self.wd)
      if err:
          return CommandResult(success=False, error=f"secret hide failed: {err}")
  ```
  `-m` re-encrypts only files whose plaintext hash changed. `-F` skips a
  registered file whose plaintext is missing (warning on stderr, exit 0).
  Without it git-secret aborts with exit 1 and would block every pull on such
  a host (probed, git-secret 0.5.0). `ShellAdapter.exe` sets `err` only on a
  non-zero exit. A hide error returns before any diff list, capture, write,
  restore or `cfg pull`. No upstream, or no git-secret: no hide call, so the
  command sequence is byte-identical to 00095. Do not reuse `_hide_secrets`:
  it runs `hide -m` without `-F`, and `status`/`commit` keep it unchanged.
  Hide needs only the public keys in `.gitsecret/keys`, so it takes no
  passphrase.

#### Feature: Recovery hint
- **Description**: Tell the user how to read a secret edit that was saved as ciphertext.
- **Inputs**: the selected path list in `_save_and_reset_divergence`.
- **Outputs**: one extra warning per reset path ending in `.secret`.
- **Behavior**: in the reset loop, right after
  `warnings.append(f"reset to HEAD, local edit in patch: {path}")`:
  ```python
  if path.endswith(".secret"):
      warnings.append(
          f"secret {path.removesuffix('.secret')} saved encrypted in patch; "
          "to read it, git apply the patch at its base commit and run git secret reveal there"
      )
  ```
  A failed reset returns before its hint, so hints match completed resets.
  `.gitsecret/paths/mapping.cfg` gets no hint (it holds only hashes). Every
  00095 message stays byte for byte.

### Capability: Documentation
Explain the secret case where 00095 documents the patch.

#### Feature: Docs and changelog
- **Description**: Describe ciphertext patches and recovery.
- **Inputs**: 00095's "Divergence patch" text in `docs/source/tools/dot.rst` and `README.md`.
- **Outputs**: updated docs and one changelog line.
- **Behavior**: `dot.rst` gets a `**Secrets in the patch:**` paragraph after
  the 00095 divergence text. Before selecting, pull re-encrypts edited
  secrets (`git secret hide -m -F`). A clashing secret is saved as its
  encrypted `.secret`, never as plaintext. To read it: clone or add a worktree
  at the patch's base commit, `git apply` the patch there, run
  `git secret reveal -f` there, copy what you need, then remove the clone.
  A `.gitsecret/paths/mapping.cfg` entry is git-secret hash bookkeeping, and
  the next hide rewrites it. If the hide step fails, pull stops before
  touching anything. README's `**Divergence patch:**` paragraph gains one
  sentence: edited secrets are saved encrypted; see `docs/source/tools/dot.rst`
  for recovery. `CHANGELOG.md` `[Unreleased]` `### Fixed`:
  `- **dot**: pull no longer overwrites a locally edited git-secret file whose upstream copy changed; the edit is saved encrypted in the divergence patch`.

## Structural Decomposition

### Repository Structure

```
src/tools/dot/
└── git/service.py                              # pull: hide step; _save_and_reset_divergence: hint
tests/tools/dot/
├── test_pull_divergence.py                     # + TestSecretHide (mocked shell)
└── test_pull_secret_divergence_two_hosts.py    # new, real git + git-secret + gpg
docs/source/tools/dot.rst                       # secrets paragraph
README.md                                       # one sentence
CHANGELOG.md                                    # Fixed entry
```

### Module: dot.git.service
- **Maps to capability**: Secret divergence save
- **Responsibility**: Hide edited secrets before selection, then hint at recovery after each secret reset.
- **Exports**:
  - `DotGitService.pull(passphrase=None, *, exclude=(), fetched=False)` - signature unchanged; gains the hide step.
  - `DotGitService._save_and_reset_divergence(exclude)` - private; gains the hint line.

### Module: dot tests
- **Maps to capability**: Secret divergence save
- **Responsibility**: Prove call order and fail-closed with a mocked shell, and recovery with real git-secret.
- **Exports**:
  - `TestSecretHide` - mocked cases in `test_pull_divergence.py`.
  - `secret_hosts` - fixture in the new two-host file.
- New symbols: `TestSecretHide`, `secret_hosts`, `test_pull_secret_divergence_two_hosts`

### Module: dot docs
- **Maps to capability**: Documentation
- **Responsibility**: User-facing recovery steps.
- **Exports**: none (prose).

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **dot.git.service**: hide step and hint, on top of 00095's `pull` and `_save_and_reset_divergence`.

### Core Layer (Phase 1)
- **dot tests (real git)**: Depends on [dot.git.service]

### Integration Layer (Phase 2)
- **dot docs**: Depends on [dot.git.service]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Hide before selection, fail closed, hint on secret resets.

**Tasks**:
- [ ] Hide step and recovery hint in `src/tools/dot/git/service.py` (no deps).
  Premise: 00095 is merged, so `pull` already calls
  `_save_and_reset_divergence`. Re-check with
  `rg -n "def _save_and_reset_divergence" src/tools/dot/git/service.py`
  (expect 1 hit). If it is absent, stop and report; do not build 00095 here.
  Add `HIDE = "cfg secret hide -m -F"` and class `TestSecretHide` to
  `tests/tools/dot/test_pull_divergence.py`, reusing `Harness`,
  `_responses`, `_restore`, `_patch_path`:
  (a) `h.shell.is_command_available.return_value = True`, `_responses()` ->
  `h.commands == [UPSTREAM, HIDE, INCOMING, STAGED, UNSTAGED, STAGED_DELETED, PULL, SUB_RESET, SUB_INIT, SUB_UPDATE, REVEAL]`;
  (b) git-secret on, `responses[HIDE] = ("gpg: no public key", "")` ->
  `error == "secret hide failed: gpg: no public key"`,
  `h.commands == [UPSTREAM, HIDE]`, `h.run` not called, `h.written == []`;
  (c) git-secret on, `{UPSTREAM: ("no upstream", "")}` ->
  `h.commands == [UPSTREAM, PULL, SUB_RESET, SUB_INIT, SUB_UPDATE, REVEAL]`;
  (d) incoming and unstaged `".gitsecret/paths/mapping.cfg\0x.secret\0"` ->
  `warnings == [patch line, "reset to HEAD, local edit in patch: .gitsecret/paths/mapping.cfg", "reset to HEAD, local edit in patch: x.secret", "secret x saved encrypted in patch; to read it, git apply the patch at its base commit and run git secret reveal there"]`;
  (e) as (d) with `responses[_restore("x.secret")] = ("denied", "")` ->
  `error == "reset failed for x.secret: denied"` and warnings hold only the
  patch line and the `mapping.cfg` reset line.
  Acceptance: `uv run pytest tests/tools/dot/test_pull_divergence.py tests/tools/dot/test_git_service.py`
  passes. Every test that predates this PRD still passes unedited, including
  `test_default_pull_fetches_then_checks_divergence_then_pulls` (git-secret
  off, so no hide). Confirm with
  `git diff --stat master -- tests/tools/dot/test_git_service.py` (empty).

**Exit Criteria**: `TestSecretHide` green; existing `test_pull_divergence.py` and `test_git_service.py` green and untouched outside the new class.

### Phase 1: Core
**Goal**: Prove the round trip with real git-secret and gpg.

**Tasks**:
- [ ] New `tests/tools/dot/test_pull_secret_divergence_two_hosts.py` (depends on: Phase 0).
  `pytestmark = pytest.mark.skipif(shutil.which("git-secret") is None or shutil.which("gpg") is None, reason="needs git-secret and gpg")`.
  Fixture `secret_hosts(monkeypatch)` returning `(origin, host_a, host_b)`:
  base `Path(tempfile.mkdtemp(prefix="dsd", dir="/tmp"))`, not `tmp_path`.
  On macOS the long pytest path pushes the gpg-agent socket past the
  Unix socket path limit and `git secret tell` fails (probed). Through
  `monkeypatch`, point the GNUPGHOME env var at `<base>/g` (mode 0o700) and set
  the four GIT_AUTHOR_* / GIT_COMMITTER_* identity vars. Generate a key with
  `gpg --batch --pinentry-mode loopback --passphrase '' --quick-gen-key dot-test@test.local default default never`.
  Bare origin, seed clone: `.gitignore` = `.buvis\n`, `git secret init`,
  `git secret tell dot-test@test.local`, write `s.txt` (`b"s base\n"`) and
  `k.txt` (`b"k base\n"`), `git secret add s.txt k.txt`, `git secret hide`,
  `git add -A`, commit, push. Hosts via `_setup_bare_host` from
  `tests/tools/dot/conftest.py`, then `secret reveal -f` on each through
  `_git(...)`. Teardown: `gpgconf --homedir <h> --kill all` (check=False)
  for `<base>/g` and every `base.glob("**/.gitsecret/keys")`, then
  `shutil.rmtree(base, ignore_errors=True)`. Pull with
  `CommandPull(shell=ShellAdapter(suppress_logging=True), dotfiles_root=str(host)).execute()`
  and no `_disable_git_secret`. A's change helper: write plaintext,
  `secret hide -m`, `add s.txt.secret .gitsecret/paths/mapping.cfg`, commit,
  push. Cases:
  (1) B writes `s.txt` = `b"s B edit\n"`, A changes it to `b"s A change\n"`.
  B pull succeeds, B `s.txt` == `b"s A change\n"`, exactly one patch,
  its bytes contain `b"a/s.txt.secret"` and not `b"s B edit"`, and
  `result.warnings` contains the `secret s.txt saved encrypted in patch; ...`
  hint. Clone origin to `<base>/fresh`, check out the patch's `# base:` id,
  `git apply` it, `git secret reveal -f` there, and `fresh/s.txt` ==
  `b"s B edit\n"`.
  (2) as (1), and B also writes `k.txt` = `b"k B edit\n"`, which upstream
  leaves alone. After the pull, B `k.txt` == `b"k B edit\n"` and the patch
  lacks `b"a/k.txt.secret"`.
  (3) as (1), but B first deletes its `k.txt` plaintext. The pull still
  succeeds (`-F`), the patch contains `b"a/s.txt.secret"`, and B `k.txt` ==
  `b"k base\n"` (re-revealed).
  Acceptance: `uv run pytest tests/tools/dot/test_pull_secret_divergence_two_hosts.py -rs`
  passes with 3 tests run, not skipped, on a host with git-secret and gpg.
  Re-check `command -v git-secret gpg` first. If either is missing, the file
  must report 3 skips, and the task report states that the real-git cases
  were not run.

**Exit Criteria**: the real-git file passes locally, or reports skips when the tools are missing (stated in the task report).

### Phase 2: Integration
**Goal**: Users can find the recovery steps.

**Tasks**:
- [ ] Docs and changelog per Feature "Docs and changelog" (depends on: Phase 0).
  Acceptance: `rg -n "git secret reveal" docs/source/tools/dot.rst README.md`
  hits `dot.rst`; `rg -n "saved encrypted" README.md` hits once;
  `rg -nF "the edit is saved encrypted in the divergence patch" CHANGELOG.md`
  hits once, under `[Unreleased]` `### Fixed`.

**Exit Criteria**: `uv run pytest -m dot` and `uv run mypy src/tools/dot src/lib` pass.

## Test Strategy

### Critical Scenarios
- **Happy path**: edited secret clashes with upstream -> saved as ciphertext, upstream plaintext revealed, patch + reveal at base rebuilds the edit.
- **Edge case**: edited secret upstream left alone -> stays dirty, not in patch, `reveal -f` returns the user's own bytes.
- **Edge case**: a registered plaintext is missing -> `-F` skips it, pull proceeds.
- **Edge case**: no git-secret, or no upstream -> no hide, 00095 sequence unchanged.
- **Error case**: hide fails -> `secret hide failed: <err>`, nothing diffed, saved, reset or pulled.
- **Error case**: reset of a `.secret` fails -> no hint for it, completed hints kept.

## Risks

- **Hide dirties more than the clash**: every locally edited secret gets new
  ciphertext, which is what `dot status` already does. Non-clashing ones are
  neither selected nor reset, and `reveal -f` decrypts them back to the user's
  bytes (two-host case 2).
- **`mapping.cfg` in the patch**: selected whenever a local secret is edited
  and upstream changed any secret. It holds hashes only, and the docs say so.
  No special case, by choice (discovery, Nice to have).
- **Pull stops after hide ran** (mixed state, save failure): the `.secret`
  files stay re-encrypted, as after `dot status`. Plaintext is untouched.
- **git-secret installed but no `.gitsecret` dir**: hide fails, so pull stops
  before merging. Today it merges and then fails at reveal (probed: both
  abort). Only a misconfigured host hits this. `dot run pull` is the manual
  way out.
- **Suffix check**: a tracked file named `*.secret` that git-secret does not
  manage gets a needless hint. That costs no bytes. `rm` and
  `encrypt_and_stage` hard-code the same suffix.
- **CI never runs real hide/reveal**: accepted (discovery Q1). The mocked call
  order in `TestSecretHide` guards the fail-closed path in CI.
- **Lands after 00095**: as of 2026-10-16, 00095 is on
  `feature/00095-dot-pull-divergence-report`, not on `master`. The Phase 0
  premise check stops the run if it is missing.
