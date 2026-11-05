# PRD 00116 assumptions

## 1: braid: discover and render rules (rules.py foundation, source layout relax)

- Tess: `make_rule`/`make_host_rule` default `body` is the literal `"..."`; every body-checking test passes one explicitly.
- Tess: `tmp_path` is already resolved, so configured and resolved paths print the same in error messages; only the first duplicate source is passed relative.
- Tess: `RuleState.as_json()` returns stored dicts unchanged, including empty inner dicts.
- Tess: `from_json` refuses `None` and list payloads ("unless payload is a dict").
- Tess: `engine.run` never links a rule-only source's rules under `<root>/skills`.
- Tess: `Settings.policy_files` values are path-like; tests compare `Path(...).resolve()`.
- Tess: `resolve_settings` needs no content in `config_root` and does not parse `.braidignore` contents.
- Tess: the bad name `tóne` keeps its spelling on disk under APFS, so the expected error text matches `iterdir`.
- Ivan: `RuleState.from_json` accepts extra top-level keys beyond the five required ones.
- Ivan: when a shared rule's name was first used by host rules on several hosts, the duplicate error names the earliest host rule's source.
- Ivan: `discover_rules` tests already-seen before legacy on the resolved source; order is not observable.

## 2: braid: file-link projections and Windows hard-link support in the engine

- Tess: `_Pass` exposes its `Result` as `.result`; `preserve_real_sources=False` is neutral for rule projections.
- Tess: a BACKUP line starts with "BACKUP " and names the destination; the backup layout under `backup_root` is not pinned.
- Tess: a recorded stale hard link whose target was rewritten is backed up and relinked on SYNC (task text), not removed as owned.
- Tess: `_backup_suffix` reads the clock through engine's module-level `datetime`; `_sync_links` finds `create_file_link` by module-global name.
- Tess: on a file-link pass `_backup` adds no drift of its own.
- Ivan: the stale file-link backup branch counts `drift += 1` before `_backup` counts `backed_up`.

## 3: braid: sync_rules projections, generated host files, instruction links and rules state

- Tess: `REMOVE` lines are exactly `REMOVE {path}`; order is directory hosts, then union shared, then union hosts.
- Tess: backups land at `backups/<suffix>/<category>/<name>`; tests glob `*/generated/codex/*` and `*/instructions/<host>/*`.
- Tess: the `LINK[...]` backend tag and link-target absoluteness are not pinned; links are checked with `resolve()`.
- Tess: without a `rules` key, top-level state keys are a subset of `{version, union, hosts, kiro}`.
- Tess: a fully current SYNC emits nothing; DRY_RUN/CHECK with nothing on disk create no agents root.
- Tess: `.braidignore` matches exact rule names; production calls `os.symlink(src, dst, target_is_directory)` without `dir_fd`.
- Tess: orphan lines across scans compared order-insensitively; a pre-existing real file at a directory-host path follows `_sync_links` backup behavior.
- Ivan: `emit` is keyword-only in `sync_rules` (`..., result, *, emit`) to satisfy ruff PLR0917 without a second per-file ignore; PRD names and order kept.
- Ivan: engine helpers reach the per-step helpers as parameters so the single function-local import holds.
- Ivan: empty `projected[host]` maps are kept in state; only empty union `hosts` maps are dropped.
- Ivan: when Kiro is not enrolled (`project_kiro` true, `kiro_root` None) the previous `projected["kiro"]` is dropped; `--no-kiro`/`--no-claude` carry it over.
- Ivan: the orphan-scan `layout` dedupes resolved sources, keeping order.

## 4: braid: summary line and CLI with generated and unmanaged counts

- Tess: test_cli.py summary literals were split into adjacent strings to satisfy ruff E501; asserted values are byte-identical.
- Tess: in SYNC each link and each generated write counts as one change; the CHECK label is not asserted, only the summary prefix.
- Tess: the `braid:` error line may carry a console marker prefix, so it is checked with `endswith`.
- Tess: `~/.copilot/copilot-instructions.md` as a hand-made regular file reports UNMANAGED.
- Orchestrator: `--no-claude` help reads "skip projecting skills and rules into the Claude root"; the plan's "into claude-root" wraps at the hyphen at 80 columns and breaks `test_parser_documents_previously_bare_options_with_help_text`.

## 5: braid: document rules (braid.rst, README, CHANGELOG)

- Ivan: the braid.rst example summary numbers are illustrative, not derived.
- Ivan: rule backup paths (`rules-backup`, `steering-backup`) and rule-name characters come from the design contract; both added to braid.rst.
