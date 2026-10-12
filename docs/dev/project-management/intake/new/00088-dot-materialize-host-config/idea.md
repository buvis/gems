# dot: keep per-host config in dotfiles via an untracked ~/.local mirror

Status: intake, not yet specced. Recorded 2026-10-12.

## Problem

Some config sits where a tool expects it but differs per machine. Today it
gets one of two outcomes, and both lose:

- tracked: one host's values leak into every other host, or
- left untracked: the file has no home, no backup through dotfiles, and
  `glean` keeps asking about it (`skip` / `machine` verdicts).

Current examples:

- `~/.config/buvis/buvis-postup.yaml` (postup reads its config here)
- `~/.config/buvis/buvis-bim.yaml`
- `~/.config/klyreon/`
- `~/.config/gita/repos.csv` (repo list differs per machine, but the
  path belongs in the public dotfiles repo): the host's file moves to
  `~/.local/.config/gita/repos.csv`, linked back to `~/.config/gita/repos.csv`
- `~/.local/bin/<script>` bound to one external volume

## Idea (from the user)

The real file lives in an untracked mirror under `~/.local`, with the same
relative tree:

```text
~/.local/.config/buvis/buvis-postup.yaml    # real, per host, never tracked
~/.config/buvis/buvis-postup.yaml  ->  link  # where postup looks
```

A git hook in the dotfiles repo materializes the links into the expected
locations, in a cross-platform way.

## Requirements

1. **R1 Mirror**: every file under the mirror root (`~/.local/.config/...`
   and the rest of the tree) maps to `$HOME/<same relative path>`.
2. **R2 Materialize**: a hook creates the missing links after the work tree
   changes. `post-checkout` alone is not enough: `dot pull` / `git pull`
   fires `post-merge`, and a rebase pull fires `post-rewrite`. Cover all
   three, plus a manual `dot <verb>` for a fresh machine.
3. **R3 Cross-platform**: macOS, Linux, Windows. Windows symlinks need
   Developer Mode or admin rights, so a fallback is needed (copy plus drift
   check, hardlink, or junction for dirs). The hook body is Python, not shell.
4. **R4 Never clobber**: if the target exists and is not the expected link
   (a tracked file, a real file, a link to somewhere else), report it and
   leave it alone. Never delete user data.
5. **R5 Idempotent and quiet**: rerunning changes nothing and prints nothing
   when all links are current. Dangling links (mirror file removed) are
   reported, not silently left or deleted.
6. **R6 Gate stays closed**: the mirror must never reach the repo. Already
   enforced: `glean check-staged` refuses `.local/` and `*/.local/*` built in
   (agent-skills `ed0303e`), and the dotfiles pre-commit hook is tracked at
   `~/.config/buvis/hooks/pre-commit`.
7. **R7 Glean knows the links**: materialized links in `$HOME` must not
   surface as untracked candidates. Glean settles links into its
   `link_roots`, so the mirror root goes there (or dot tells glean).
8. **R8 Hooks reach every machine**: the user requires the pre-commit gate
   on every machine. Hooks are tracked in the work tree, but
   `core.hooksPath` lives in the bare repo's config, which is not tracked.
   dot must set `core.hooksPath=~/.config/buvis/hooks` on setup, and `dot
   status` (or every dot command) must warn when it is unset or the hook is
   missing. Chicken-and-egg: the hook cannot install itself, so this is dot's
   job, and it must happen before the first checkout on a new machine so the
   R2 hooks fire.
9. **R9 All-interface**: per the gems all-interface rule, materialize and
   link status go through one command class that the hook, CLI and TUI all
   call (`DotGitService` is the existing seam).

## Open questions

- Mirror root: `~/.local/.config/...` as proposed, or `~/.local/share/dot/home/`
  (XDG data dir) with the full `$HOME` tree inside?
- Link kind per platform, and whether dirs link whole (`klyreon/`) or per file.
- Should dot also *create* a mirror entry (`dot localize <path>`: move file
  into mirror, leave link), or is that manual?
- Does the mirror need its own backup, since dotfiles no longer covers it?
  (Kopia / Backblaze may already cover `~/.local`.)
- Bootstrap: dot has no clone/setup command today. Is R8 a new
  `dot setup`, or a check inside existing commands?
