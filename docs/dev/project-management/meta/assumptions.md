# Assumptions

PRD 00105: no worker assumptions reported. Planning resolutions are recorded in state and the build evidence.

## PRD 00110 rework, task 6: isolate planning failures

- Tess and timestamp-boundary Tess: none.
- Initial Ivan assumed a failed plan could retain raw configured output; timestamp collision regressions disproved this and the repair superseded it.
- Initial Ivan matched failure reasons to the existing `_run_instance` format and chose the Fixed changelog wording.
- Repair Ivan assumed capability outputs use `now.strftime`; verified against the sole registered TarArchive capability.
- The one-shot style fixer assumed reading Runner and CHANGELOG was allowed despite its test-only allowlist. It made no changes; the 52-line test style violation remains recorded under the workflow's one-shot cap.

## PRD 00110 rework, task 7: preserve plan input compatibility

- Tess: none.
- Initial Ivan prioritized "no source configured" when both paths are empty, matching existing run behavior.
- Initial Ivan kept a stamp-expanded output and `replaces=False` when source is empty; no filesystem probe occurs for invalid configuration.
- Repair Ivan: none.
- Initial Ivan verified 87 filtered backup tests instead of the supplied file. The repair and coordinator subsequently ran the exact task file: all 58 tests passed.

## PRD 00110 task 7: final verification repair

- Isolated Tess contract correction: none. The old empty-engine fail expectation contradicted the required fallback and was corrected without changing unknown-engine rejection.
- Final closure Ivan: none. Shared parsing, missing-input selection, and path setup now each have one implementation.
- Process-only verification isolation clears inherited agent Git identity/config overrides and uses an ephemeral supported Postup roots override. HOME and persistent configuration are unchanged.
