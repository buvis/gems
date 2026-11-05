# PRD 00115 assumptions

## 2: Port the engine test suites to tests/tools/braid and register the braid marker

- `isolate_braid_environment` creates the `buvis-config` directory (the contract calls it "empty") but does not create `tmp_path/"home"`, so engine `not ...exists()` asserts stay meaningful.
- `test_configured_sources_support_comments_home_and_relative_paths` keeps its reference `agent-skills` config path verbatim: it calls `read_configured_sources` directly, under the "rewrite only imports and helpers" rule.
- `test_check.py` keeps the reference module docstring (PRD 00014, agoge note) verbatim.
- The `isolate_braid_environment` docstring is Ivan's own one-line wording.
- Orchestrator: `tests/tools/braid/__init__.py` was later deleted (commit a69c6ea5). Under `--import-mode=importlib` it registered the test dir as package `braid` and shadowed `src/tools/braid` (found by Devon in task 1). This differs from the design doc's module list.
- Deviation: the reference's inline mypy ignore on `error.winerror = 1314` was dropped because the aegis suppression hook blocks it. gems runs mypy only on `src/`, so nothing checks that line.

## 1: Port the braid engine and Kiro logic into src/tools/braid/domain

- Tess (strengthen): test 9 assumes `atomic_write_text` calls `os.replace` through the `os` module and removes its temp file on failure. Test 7 assumes `kiro.py` calls `shutil.copymode` by module attribute. The expected link lines assume `Settings.platform` defaults to posix on the test host.
- Ivan: `model.py` and `kiro.py` carry no `__all__`; only `engine.py` re-exports, per the contract. `ruff format` reflowed the copied code to gems' line length (layout only). `Callable`/`Iterable` moved under `TYPE_CHECKING`.
- Ivan (style fix): `run` is 49 lines, one under the 50-line limit. A shared `_project_host` helper builds the Claude and Kiro projections that were two identical blocks.
- CHANGELOG `[Unreleased]` Added entry for braid landed with the engine commit (a feat commit needs it); task 5 verifies it rather than adding it.

## 4: Write tests/tools/braid/test_cli.py with CliRunner

- The one-line error asserts require exactly one output line with the bare error phrase, and that line must be the last output line.
- The option-rejection tests and the second `--check` run in the Kiro enrollment test also pass the roots and `--source`, because the CLI has no `_repository_root` source.
- The OS-error and machine-policy tests do not pass `--no-claude`/`--no-kiro`.
- The `--check` drift test treats the last output line as the summary (starts with `braid: `, contains `drift`).
- The long-line test expects the link target to be `skill.resolve()` and the destination to be the unresolved `tmp_path/home/.agents/skills/portable` (`tmp_path` is already resolved).
- The help-text test compares whitespace-normalized output.
- The old-config test writes one absolute path per line in `.config/agent-skills/sources.d/personal`.

## 3: Add the braid Click CLI, settings, CommandCompose and wheel wiring

- Tess (strengthen): the summary is the last output line on success. The parametrized `--kiro-root X` rejection case uses a relative `X`, which is never resolved because the rejection runs first. A `--kiro` run stores an empty Kiro agents list.
- Ivan: `get_settings` is imported from `buvis.pybase.configuration` and `CommandResult` from `buvis.pybase.result`; tests, mypy and `--help` confirm both.
- Orchestrator: this `feat` commit stages no CHANGELOG change. The `[Unreleased]` braid entry from the task 1 commit already covers the whole user-visible feature.

## 5: Document braid in README, AGENTS.md, Sphinx docs and CHANGELOG

- The AGENTS.md tree line uses the tree's real 4-space prefix.
- The README `### braid` section sits at the end of the file, after `### bim doc subsystem`, because there is no plain `### bim` section.
- The summary-line example in `braid.rst` uses made-up counts.
- Orchestrator corrections after Ivan: the Kiro agent backup path is `<kiro_root>/agent-backup/<stamp>/agents/`. A non-empty `BUVIS_BRAID_KIRO_ROOT` alone enrolls Kiro, an empty one counts as unset, and a saved enrollment cannot move roots (checked against `kiro.py:select_kiro`). The CHANGELOG bullet's appended sentence now joins with a semicolon.
- Out of scope, already wrong before this task: `docs/source/tools.rst` says "all 16 CLIs" while its table lists 18 tools, and the README CLI list omits klyreon and postup.
