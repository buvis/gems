# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **pidash**: doubt-review phase in pipeline (CATCHUP → PLANNING → WORKING → REVIEWING → DOUBT → DONE)
- **pidash**: dedicated Doubts panel for doubt review findings
- **pidash**: render `[C{n}]` cycle tags in magenta, `[DOUBT]` tags in cyan
- **dot**: `rm` command for removing files from dotfiles tracking (handles git-secret cleanup)
- **dot**: TUI mode - interactive terminal UI for dotfiles management (`dot` or `dot tui`)
- **dot**: TUI colored diff preview with auto-update on cursor movement
- **dot**: TUI commit modal, gitignore modal, delete confirmation dialog
- **dot**: TUI push/pull/refresh keybindings (p/P/r)
- **dot**: TUI space key as stage/unstage toggle

### Fixed

- **pidash**: escape brackets in task names to prevent Rich markup swallowing
- **dev**: `release local` reliably restores pyproject.toml after build

## [0.4.0] - 2026-03-22

### Added

- **pidash**: new Textual TUI dashboard for monitoring autopilot PRD cycle status
- **pidash**: attention overlay when Claude needs permission approval
- **pidash**: animated braille spinner for active phases, task list with status markers
- **dot**: report unpushed/unpulled commits in status
- **dot**: skip push when nothing to push, hint GPG on pull failure
- **dev**: `release local` for .devN test builds
- **dev**: automate pyproject.toml tool wiring for new tools
- **ci**: split test matrix into lib + per-tool jobs

### Changed

- **zettel**: flatten fixers/upgrades directory structure
- **config**: consolidate paths, source, generators into fewer modules
- **pybase**: move DirTree from shared library to muc (sole consumer)
- **fctracker**, **pinger**: return CommandResult on error instead of raising exceptions
- **console**: exit with code 1 in panic()
- **deps**: replace bincode with rmp-serde, bump cache version to 4
- **deps**: upgrade textual 3.7→8.1, vite 8, marked 17

### Fixed

- **fren**: decode RFC 2047 encoded EML headers before slugifying
- **fren**: slug lowercase and eml timestamp format
- **bim**: run svelte-kit sync before vite build
- **dot**: replace pexpect with subprocess.run in shell interact
- **dot**: stage .gitignore in encrypt to prevent plaintext staging
- **dot**: push when upstream unknown, add supports dirs
- **dot**: add untracked files when adding a directory
- **pybase**: return actual stderr on failure, discard stderr on success

## [0.3.2] - 2026-02-24

### Added

- **dot**: staged/unstaged status, unstage command, commit positional arg

## [0.3.1] - 2026-02-24

### Added

- **dot**: encrypt and run commands

### Fixed

- **dot**: show deleted/new/renamed files in status, add missing pull steps

## [0.3.0] - 2026-02-24

### Added

- **fren**: file renamer toolkit — slug, directorize, flatten, normalize commands
- **morph**: file conversion toolkit — html2md and deblank commands
- **netscan**: network scanner tool
- **puc**: photo utility collection tool
- **sysup**: system update tool
- **vuc**: video utility collection tool
- **muc**: cover command for duplicate cover cleanup
- **dot**: pull, commit, push commands
- **ci**: SLSA build provenance attestation and SBOM generation

### Changed

- **console**: extract report_result, require_import, validate_path helpers

### Fixed

- **fren**: narrow broad except in EML slug fallback
- **morph**: avoid unlinking before restore in deblank
- **ci**: downgrade upload/download-artifact to v4

## [0.2.3] - 2026-02-20

### Fixed

- **jira**: populate environment field on issue creation

## [0.2.2] - 2026-02-20

### Fixed

- **bim**: sync description from zettel to linked jira issue
- **rust**: preserve reference section order using IndexMap

## [0.2.1] - 2026-02-20

### Fixed

- **config**: skip world-writable check on Windows

## [0.2.0] - 2026-02-20

Initial release.

### Added

- **pybase**: shared library — adapters, configuration, filesystem, formatting utilities
- **zettel**: subsystem with domain logic, Jira integration, and Rust extension (PyO3) for YAML scanning
- **bim**: BUVIS InfoMesh CLI — query engine with expression language, multiple output formats (table, json, jsonl, html, pdf, tui, kanban), web dashboard (SvelteKit), create/edit/show/delete/archive/format/import/sync commands
- **dot**: dotfiles manager with status and add commands
- **fctracker**: foreign currency account tracker
- **hello_world**: sample script template
- **muc**: music collection tools
- **outlookctl**: Outlook CLI
- **pinger**: ICMP ping utilities
- **readerctl**: Readwise Reader CLI
- **zseq**: Zettelsequence utilities
- **zettel**: metadata cache for fast filtered queries, recurrence parsing, expand directive, subclass instantiation
- **config**: Pydantic-based settings with Click option generation
- **ci**: GitHub Actions with test matrix, coverage, ruff lint, mypy, dep audit, GitHub releases

[Unreleased]: https://github.com/buvis/gems/compare/gems-v0.4.0...HEAD
[0.4.0]: https://github.com/buvis/gems/compare/gems-v0.3.2...gems-v0.4.0
[0.3.2]: https://github.com/buvis/gems/compare/gems-v0.3.1...gems-v0.3.2
[0.3.1]: https://github.com/buvis/gems/compare/gems-v0.3.0...gems-v0.3.1
[0.3.0]: https://github.com/buvis/gems/compare/gems-v0.2.3...gems-v0.3.0
[0.2.3]: https://github.com/buvis/gems/compare/gems-v0.2.2...gems-v0.2.3
[0.2.2]: https://github.com/buvis/gems/compare/gems-v0.2.1...gems-v0.2.2
[0.2.1]: https://github.com/buvis/gems/compare/gems-v0.2.0...gems-v0.2.1
[0.2.0]: https://github.com/buvis/gems/releases/tag/gems-v0.2.0
