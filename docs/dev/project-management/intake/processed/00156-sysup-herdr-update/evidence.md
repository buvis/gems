# Herdr maintenance evidence

Read-only inspection on 2026-11-15. No updates, restarts, mod checks, agents,
or writes to the Herdr home were performed.

## Installed contract

- `herdr-app --version` returned `herdr-app 0.1.16`. This identifies the
  invoked binary, not independently the version of a running window.
- `herdr-app commands` lists `app.check_updates`, `app.update_core`, and
  `app.update`. The last restarts into a downloaded update; the core command
  describes keeping terminals alive.
- `herdr-app status` returned window state and an empty errors list. It
  contained no update progress, readiness, completion, or version field.
- The generated `~/.config/herdr-app/AGENTS.md`, lines 669-672 and 750-762,
  says the installed app downloads updates itself, updates core on the first
  launch after an app update, and leaves package-managed cores to their
  package manager. Source builds do not update themselves.
- The generated `herdr.d.ts`, lines 330-345, exposes update state through
  the in-mod `updates()` API. That is not a documented CLI query. No claim
  about synchronous completion or response shape of update commands was
  verified; none was executed.
- The installed guide explicitly says `herdr-app check` runs mod init code;
  exec, core calls, and file writes still run unless the mod guards them.
  Therefore a blanket mod check is not a read-only health audit.

## Clone provenance

- `mods/my-tabs/mod.json` and `mods/my-spaces/mod.json` contain
  `cloned_from: {name: tabs|spaces, version: 0.1.13}`.
- `layouts/buvis.json` contains `cloned_from: {name: my-main, version: 0.1.13}`.
  `layouts/my-main.json` is absent. A source can be another personal clone,
  not a shipped layout; do not assume all provenance resolves upstream.
- `installed.json` is an object of shipped asset hashes. Mod keys are plain
  names; layout keys use `layout:<name>`. It has no app-version field.
- A different clone version is a review signal, not proof of changed upstream
  content or incompatibility. Equal versions do not prove compatibility.

## Existing ownership

- `src/tools/sysup/default.yaml` already runs the Herdr-home hmod shim with
  `update --all` after mise, guarded by macOS, binary, shim, and window checks.
- The shim points to the local `jonathan-fielding/herdr-mod-updater` checkout;
  inspected revision: `224a08e694aded5836530fa588c6e000543baf7c`.
- That checkout's `src/inventory.ts` distinguishes shipped mods, installer-owned
  mods, community mods, and user clones. It refuses to link user clones.
- Its `src/check.ts` excludes user clones from upstream checks. Its
  `src/update.ts` skips edited, unlinked, error, source-changed and
  first-update-pending mods during update-all. It does not port personal
  layouts or mods. No hmod command was run during this inspection.

## Repository integration

- `src/tools/sysup/capabilities/__init__.py`: capabilities declare inputs and
  yield `StepResult`; the runner stamps the configured command name.
- `src/tools/sysup/step_result.py`: warned results are nonfatal; failed and
  unknown results are red and make the current run fail.
- `src/tools/sysup/attention.py`: any non-ok result persists; a fully healthy
  check clears its command's entry; unselected commands retain their entries.
  Reuse this mechanism rather than inventing clone-specific state.
- `Runner._run_use` avoids invoking capabilities in dry-run mode.
- No nested AGENTS.md was found under docs, src, or tests in this checkout.
