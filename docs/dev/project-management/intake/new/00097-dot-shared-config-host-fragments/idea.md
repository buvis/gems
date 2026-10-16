# dot: share a config file across hosts while keeping its host-specific parts local

Status: new, idea only. Recorded 2026-10-16.

## Problem

Some tracked config is almost entirely shared, but a few values in it differ
per machine. Tools also rewrite these files on their own. Neither of dot's two
outcomes fits:

- **Tracked as is**: each host writes its own values, so every sync flips the
  file between machines and causes conflicts.
- **Localized** (`dot localize`, PRD 00090): the whole file moves to
  `~/.local/<path>` and is linked back. That fixes the host values but stops
  sharing the other 95% of the file. A shared hook added on one machine never
  reaches the other, and the dotfiles repo only records a link. That is no
  better than untracking the file and keeping a local copy.

Case that surfaced it (2026-10-16), with home paths that differ per machine:

- `~/.claude/settings.json` (20 lines contain `/Users/bob`) and
  `~/.codex/hooks.json` (22 lines) are tracked. Most of the hooks, permissions
  and plugins are shared. Only the absolute home prefix in the hook commands
  differs.
- The herdr agent-activity plugin rewrites its hook entries in both files on
  every herdr startup (`bin/cli.mjs` `startup()` -> `applyHooks`), using the
  absolute path of its `hook.sh` shim. A hand edit to `$HOME/...` is undone on
  the next start. Each host writes its own path, so the tracked files flip.
- herdr's `~/.config/herdr/plugins.json` hit the same wall. It had to be
  untracked, and a portable `plugins.txt` list (synced by a sysup step) took
  its place.

## Idea (from the user)

Define the common content of such a file once, and fill in the machine-specific
parts every time dot pulls changes.

## Proposed solution

Two layers, built in order. Layer 1 covers every case seen so far.

### Layer 1: placeholder substitution as a git clean/smudge filter (recommended)

Track the file normally, but store host values as placeholders. Git already
has the hook points for this:

- **clean** (index <- work tree, on `add`/`status`/`diff`): replace host
  values with tokens, e.g. `/Users/bob` -> `@HOME@`.
- **smudge** (work tree <- index, on checkout/merge/pull): replace tokens with
  this host's values.

```text
~/.gitattributes (tracked)
  .claude/settings.json   filter=dot-host
  .codex/hooks.json       filter=dot-host

bare repo config (untracked, set by dot setup, like core.hooksPath in R8 of 00088)
  filter.dot-host.clean    = dot filter clean %f
  filter.dot-host.smudge   = dot filter smudge %f
  filter.dot-host.required = true
```

Why this first:

- **Tool writes survive.** When the plugin writes `/Users/alice/.config/...`,
  clean turns it back into `@HOME@/.config/...`. The index sees no change, so
  nothing flips and no conflict follows. A render-from-template design would
  overwrite such writes on the next pull, or need a separate capture step.
- **No new file layout.** The real file stays where the tool expects it: no
  link, no `.local` mirror, no manifest entry. `dot pull` needs no extra step
  because git runs smudge itself whenever it writes the file.
- **Diffs stay readable.** `dot diff` shows placeholders, so the shared change
  is what you review.

Design points:

- **Variables**: start with `HOME` only (YAGNI). Allow `USER` and `HOST` later
  only for a real case. Values come from the running host; optional overrides
  in a per-host file under the 00088 mirror (`~/.local/.config/buvis/...`).
- **Match safely**: replace `HOME` only when it is a whole path prefix, i.e.
  followed by `/`, `\`, `"` or end of line, so `/Users/bob` never hits
  `/Users/bobby`. On Windows, also handle the JSON-escaped `C:\\Users\\bob`.
  Pick a token that cannot appear in real content.
- **Cross-platform**: `dot filter` is Python, like the 00088 hook body. No
  `sed`.
- **All-interface**: clean/smudge go through one command class (the
  `DotGitService` seam), and the CLI subcommand only wraps it.
- **One-time migration**: setting up the filter on an existing checkout needs
  `git add --renormalize -- <paths>` so the index holds tokens. `dot setup`
  does this and reports it.
- **Fail loud**: with `required = true`, a missing `dot` fails the git command
  instead of committing raw host values. `dot status` warns when
  `.gitattributes` names `filter=dot-host` but the bare repo config lacks the
  driver. This is the same chicken-and-egg as `core.hooksPath` in 00088 R8.
- **Glean/gate**: no change. The files stay tracked and only the stored bytes
  differ.

### Layer 2: structural host overlay (only if a host-only key is ever needed)

For a case where a host needs extra or different keys rather than different
values (e.g. a hook that only one machine runs): track a shared base and keep a
host overlay in the 00088 mirror. dot deep-merges them into the target on pull
and materialize.

```text
~/.claude/settings.json            rendered, untracked (or filtered)
~/.claude/settings.base.json       tracked, shared
~/.local/.claude/settings.json     host overlay, never tracked
```

Not recommended now. A tool writing to the rendered file forces dot to split
each change between base and overlay, and arrays (hook lists) make that split
ambiguous. Build it only when a real host-only key appears. Layer 1 covers
every case seen so far.

### Rejected

- **Hand-written `$HOME` in hook commands**: the agent-activity plugin
  rewrites them to absolute paths on every startup.
- **Localize plus manual sync**: drops shared content, which is the problem
  itself.
- **Per-host branches**: shared changes then need a merge on every host.

## Requirements (draft)

1. **R1 Placeholder round-trip**: for a file with `filter=dot-host`, the index
   holds `@HOME@` where the work tree holds this host's home path, and
   checkout restores this host's path. clean(smudge(x)) == x for tokenized
   content.
2. **R2 Tool writes are a no-op**: rewriting a filtered file with this host's
   absolute paths produces no `dot status` change.
3. **R3 Safe matching**: only whole-path-prefix matches are replaced, and a
   test covers the `/Users/bob` vs `/Users/bobby` case.
4. **R4 Setup and drift check**: `dot setup` writes the filter driver into the
   bare repo config and renormalizes the listed paths. `dot status` warns when
   the driver is missing.
5. **R5 Cross-platform**: macOS, Linux and Windows (including JSON-escaped
   backslash paths).
6. **R6 Opt-in per path**: only paths listed in the tracked `.gitattributes`
   are filtered. A `dot share <path>` (or similar) adds the attribute line and
   renormalizes, mirroring `dot localize`.

## Open questions

- Command name: `dot share`, `dot portable`, or a flag on `dot localize`?
- Should `HOME` be the only built-in variable, or should `USER` ship too (a
  username also appears inside paths)?
- Token syntax: `@HOME@` vs `{{HOME}}`. The token must never occur in real
  content and must survive JSON/TOML/YAML unescaped.
- Once Layer 1 lands, should herdr's `plugins.json` go back to being tracked
  through the filter instead of the `plugins.txt` sync? It still churns on
  `installed_unix_ms` with every plugin install, so probably not.
