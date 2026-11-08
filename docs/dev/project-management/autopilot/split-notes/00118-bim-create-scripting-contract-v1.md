# Split note: 00118-bim-create-scripting-contract-v1.md
planned=5 prd_tasks=5 expansion=1.00 reasons=module_drift

## . (UNLISTED)

- 5 Document scripting v1 and local identity behavior: CHANGELOG.md, README.md

## tests/lib/zettel/entities/zettel (UNLISTED)

- 1 Use local-time date and offset-faithful identity: tests/lib/zettel/entities/zettel/test_zettel_consistency_service.py

## docs/source/tools (listed)

- 5 Document scripting v1 and local identity behavior: docs/source/tools/bim.rst

## src/lib/buvis/pybase/zettel/application/use_cases (listed)

- 2 Prepare body and reserve collision-safe note ids: src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py

## src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers (listed)

- 1 Use local-time date and offset-faithful identity: src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_date.py, src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py

## src/tools/bim (listed)

- 4 Expose create JSON body source dry-run flags and failure exits: src/tools/bim/note_write_cli.py, src/tools/bim/note_read_cli.py
- 5 Document scripting v1 and local identity behavior: src/tools/bim/SKILL.md

## src/tools/bim/commands/create_note (listed)

- 3 Add shared scriptable create command and adapter wiring: src/tools/bim/commands/create_note/create_note.py

## src/tools/bim/commands/serve (listed)

- 3 Add shared scriptable create command and adapter wiring: src/tools/bim/commands/serve/_actions.py

## src/tools/bim/params (listed)

- 3 Add shared scriptable create command and adapter wiring: src/tools/bim/params/create_note.py

## src/tools/bim/tui (listed)

- 3 Add shared scriptable create command and adapter wiring: src/tools/bim/tui/create_note.py

## tests/lib/zettel/application (listed)

- 2 Prepare body and reserve collision-safe note ids: tests/lib/zettel/application/test_create_zettel_use_case.py

## tests/lib/zettel/entities/zettel/fixers (listed)

- 1 Use local-time date and offset-faithful identity: tests/lib/zettel/entities/zettel/fixers/test_set_default_date.py, tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py

## tests/tools/bim (listed)

- 3 Add shared scriptable create command and adapter wiring: tests/tools/bim/test_create_note.py
- 4 Expose create JSON body source dry-run flags and failure exits: tests/tools/bim/test_note_write_cli.py, tests/tools/bim/test_bim_cli_handlers.py, tests/tools/bim/test_note_read_cli.py
