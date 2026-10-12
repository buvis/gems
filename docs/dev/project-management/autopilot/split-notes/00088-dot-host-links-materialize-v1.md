# Split note: 00088-dot-host-links-materialize-v1.md
planned=9 prd_tasks=6 expansion=1.50 reasons=module_drift

## . (UNLISTED)

- 9 Document host-links manifest, dot materialize and hooks: README.md

## docs/source/tools (UNLISTED)

- 9 Document host-links manifest, dot materialize and hooks: docs/source/tools/dot.rst

## src/tools/dot/commands/links (UNLISTED)

- 6 Add CommandMaterialize, CommandLinkStatus and `dot materialize [--hook]`: src/tools/dot/commands/links/__init__.py, src/tools/dot/commands/links/links.py

## src/tools/dot/commands/materialize (UNLISTED)

- 6 Add CommandMaterialize, CommandLinkStatus and `dot materialize [--hook]`: src/tools/dot/commands/materialize/__init__.py, src/tools/dot/commands/materialize/materialize.py

## src/tools/dot (listed)

- 6 Add CommandMaterialize, CommandLinkStatus and `dot materialize [--hook]`: src/tools/dot/cli.py

## src/tools/dot/commands/status (listed)

- 7 Append host link warnings to `dot status` (CommandStatus): src/tools/dot/commands/status/status.py

## src/tools/dot/git (listed)

- 5 Add DotGitService.hooks_path() reading core.hooksPath: src/tools/dot/git/service.py

## src/tools/dot/hostlinks (listed)

- 1 Implement host-links manifest parsing (dot/hostlinks/manifest.py): src/tools/dot/hostlinks/manifest.py
- 2 Implement host link reconciliation (dot/hostlinks/linker.py): src/tools/dot/hostlinks/linker.py
- 3 Implement relink git hook installer (dot/hostlinks/hooks.py): src/tools/dot/hostlinks/hooks.py
- 4 Add hostlinks package exports (dot/hostlinks/__init__.py): src/tools/dot/hostlinks/__init__.py

## src/tools/dot/tui (listed)

- 8 TUI: link problem count in status bar and key L to materialize: src/tools/dot/tui/app.py

## src/tools/dot/tui/screens (listed)

- 8 TUI: link problem count in status bar and key L to materialize: src/tools/dot/tui/screens/main.py

## src/tools/dot/tui/widgets (listed)

- 8 TUI: link problem count in status bar and key L to materialize: src/tools/dot/tui/widgets/status_bar.py
