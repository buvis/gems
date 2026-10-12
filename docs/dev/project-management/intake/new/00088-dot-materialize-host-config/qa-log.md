# Q&A log: 00088 dot materialize host config

## 2026-10-12

- **Which `.local` must never reach dotfiles?** Both `~/.local` and nested
  `<dir>/.local/`. The fctracker encrypted CSVs that lived under
  `~/.local/share` were untracked rather than exempted.
- **Must the pre-commit gate exist on every machine?** Yes. Done so far:
  the rule is built into glean, and the hook is tracked at
  `~/.config/buvis/hooks/pre-commit` and wired through `core.hooksPath`.
  Open: setting `core.hooksPath` on a new machine (R8).
- **Where do per-host files live?** The user's idea: an untracked mirror
  under `~/.local`, with a hook materializing links into the expected
  locations. Example: postup reads `~/.config/buvis/buvis-postup.yaml`,
  and the real file lives under `~/.local/.config/buvis/`.
- **Another example?** `~/.config/gita/repos.csv`: host-specific, wanted in
  the public dotfiles repo. The machine's copy must move to
  `~/.local/.config/gita/repos.csv` with a link at `~/.config/gita/repos.csv`.
  This leans toward dot doing the move (the `dot localize` open question).
