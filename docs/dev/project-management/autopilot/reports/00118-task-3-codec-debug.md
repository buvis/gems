# Task3 dependency-contract correction

## Failure Capture
- Session / task: /root/ivan_3_recovery, task3.
- Goal in progress: shared scripted command through existing library persistence.
- Error:47 passed/10 failed; failing tests require raw body substrings or exact unencoded section tuples after formatting/readback.
- Last successful step: six-file implementation and47 passing cases; no tests changed.
- Last failed command: uv run pytest tests/tools/bim/test_create_note.py -q --tb=line.
- Repeated pattern seen: raw-data assertions are applied to the established Markdown codec boundary.
- Environment assumptions to verify: whether formatting changes predate task3 and whether bypassing them is permitted.

## Recovery Action
- Diagnosis chosen: spec/test boundary gap, not a command implementation failure. PRD/design require reuse of the existing formatter/repository. A direct control using only unchanged ZettelFactory/MarkdownZettelRepository reproduces the transformation without CommandCreateNote.
- Smallest action taken: independently serialize literal section content and read it back in a temporary scratch directory; no feature command involved. Before: [('# Test', 'Template default\n\nFirst\n\nSecond'), ('# Details', 'Keep this section')]. After: [('# Test', '\nTemplate default  \n\nFirst  \n\nSecond  \n\n'), ('# Details', '\nKeep this section  \n\n---')]. Existing formatter adds Markdown hard-break spaces and its footer; parser retains section framing.
- Why this is safe: keep product formatter/parser untouched, preserve exact meaningful content assertions, and correct the test boundary using existing public behavior. No failed product behavior is relaxed.
- What evidence proves the correction: same57 task cases green through unchanged persistence, and raw body normalization remains independently covered by task2's60 cases.

## Agent Self-Debug Report
- Session / task: task3 verification.
- Failure:10 test assertions contradicted required dependency reuse.
- Root cause: public type snapshot omitted existing serialization/readback transformations, which constructors initially masked.
- Recovery action: append observed dependency contract to canonical task; use the remaining fourth total Tess dispatch for this bounded test-contract correction, with no further authoring/quality loop. Never modify codecs or let Ivan change tests.
- Result: partial, correction pending.
- Token / time burn risk: bounded to one remaining Tess dispatch and one implementation verification.
- Follow-up needed: re-run exact task tests and all mandatory cleanup/style/per-task review.
- Preventive change to encode later: supply dependency behavior, not signatures alone, when real round-trip assertions cross established codecs.

The deterministic task diagnosis also found abbreviated dangling serve/TUI paths; both were anchored to their known PRD paths through task-set-body, and re-diagnosis passed. The feat commit is not yet landed: pre-commit correctly rejected a missing PLR0917 suppression on the pinned six-argument constructor; the bounded feedback repair must include it before the single commit retry.
