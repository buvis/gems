# dot pull: save divergent secret plaintext

Status: processed, specced as PRD 00097. Recorded 2026-10-16.

## Idea (from the user)

Problem (deferred from PRD 00095, see the "Design review dispositions" item 2 in
docs/dev/project-management/designs/00095-dot-pull-divergence-report-v1-design.md and
prds/done/00095-dot-pull-divergence-report-v1.md):

- dot pull now saves uncommitted edits that clash with incoming commits to a git
  apply-able patch in ~/.local/share/dot/divergence/ (0o700), resets them to HEAD,
  then pulls (DotGitService.pull -> _save_and_reset_divergence in
  src/tools/dot/git/service.py).
- git-secret plaintext files are gitignored; only <file>.secret is tracked.
  DotGitService.status() runs `cfg secret hide -m` first, but pull() never does.
  So a locally edited plaintext secret whose .secret changes upstream is invisible
  to the staged/unstaged lists: no patch is saved, and the final
  `cfg secret reveal -f` silently overwrites the edit. This predates 00095 (not a
  regression) but is the same data-loss class 00095 closed for normal files.

Decisions the PRD must settle (recommend one each, with tradeoffs):

1. Mechanism: run `secret hide -m` before divergence selection so the edited
   .secret becomes dirty and gets saved (patch holds ciphertext; recovery = git
   apply then secret reveal), versus saving plaintext bytes directly (plaintext
   secrets on disk outside git, even with 0o700).
2. Side effects of hiding on pull: other .secret files become dirty without
   clashing with upstream; hide failure handling (pull must stop before any
   reset); hosts without git-secret installed.
3. Recovery wording in docs and pull messages so the user knows how to get the
   plaintext back.
4. Tests: mocked-shell cases in tests/tools/dot/test_pull_divergence.py style,
   and a real-git two-host case if git-secret/gpg can run in tests (check how
   existing tests handle git-secret; tests/tools/dot/conftest.py has
   _disable_git_secret); otherwise state the gap.

Out of scope: pull.rebase=true behavior, concurrent same-second pulls (both
noted in the 00095 design doc).
