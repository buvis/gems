# Decision Audit Log: 00150-bim-tiromex-format-v1

PRD: `00150-bim-tiromex-format-v1.md`
Started: 2026-11-23T21:59:42Z
Completed: 2026-11-23T21:59:42Z
Autonomous: 9  |  Deferred: 1  |  Doubts: 0

### [autonomous] 2026-11-23T21:59:42Z

**Decision**: Design for PRD 00150: thin tx layer over ZettelData; rules read the raw body; one additive src/lib edit (stderr keyword on ConsoleAdapter.warning and failure)

**Choice**: design accepted after 3 dispatches plus one extra Claude review; all raised blockers fixed except one resolved by contract

**Rationale**: codex twice asked for last-separator backmatter parsing; discovery M5 defines tiromex notes as bim notes and both bim parsers split at the first --- line, so the design forbids a --- line in a tiromex body (parse-error) and flags it to the owner. Open non-blocker: an unreadable date value gets no diagnostic. Existing bim defects reported, not fixed: repeated backmatter keys flattened, duplicate H1 on H1-only body with backmatter, lossy section splitting.

### [autonomous] 2026-11-23T21:59:42Z

**Decision**: `bim tx <cmd> --help` runs the `tx` group callback before Click builds the subcommand context; `bim tx validate --help` prints the stderr line "maintenance has never run". Help invocations should not warn or load settings; the test at tests/tools/bim/tx/test_cli.py:135 checks only options and exit code.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-23T21:59:42Z

**Decision**: `_check_sources` accepts `mirror:/x` (empty root name) and `mirror:root/` (empty path part); the source-shape contract needs a root name before the first `/`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-23T21:59:42Z

**Decision**: A parseable note with `doubts: 42` or `doubts: true` crashes status: the disagreement counter iterates the scalar without checking its type. Guard for a list and add malformed-metadata status tests.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-23T21:59:42Z

**Decision**: `_ZETTEL_TYPES` is defined twice: a tuple at new.py:28 and a list at tx_cli.py:20, each filtering `wiki-article` out of `CONCEPT_NOTE_TYPES`. Keep one definition and reuse it. tx_cli.py:12 also imports format.py at module level to build the click.Choice lists, pulling the zettel parser and formatter into every `bim` start, while doc_cli.py and note_read_cli.py import their command code lazily; move the Choice values to a light constants module or build them lazily to keep the AGENTS.md lazy-import convention.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-23T21:59:42Z

**Decision**: A relation targeting a symlink loop escapes validation as `RuntimeError` or `OSError`: `confine` does not normalize resolution failures, while graph callers catch only `ValueError`. Convert these failures to contextual `ValueError` diagnostics and add a loop-target regression test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-23T21:59:42Z

**Decision**: The invalid-choice integration test passes when the entire `tx` command is absent, as confirmed by replay: exit 2 and no files do not identify the intended rejection. Assert the specific invalid-choice or missing-title diagnostic for each case.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-23T21:59:42Z

**Decision**: Cycle 1 decision gate: consolidate_findings left three paraphrase pairs (R4+R12, R10+R15, R13+R14) as single-voice rows

**Choice**: merged each pair into one 2/4 row in review-1.md (note in file); fixed R1, R2, R3 (HIGH), R4, R10, R13 as 4 D1 tasks; discarded 16 single-voice medium/low rows to the ledger

**Rationale**: each pair names one defect at the same file and line from two reviewers; review-close refuses single-voice fixes, so the table had to carry the true consensus; 00120 review set the coordinator-merge precedent

### [autonomous] 2026-11-23T21:59:42Z

**Decision**: Cycle 2 decision gate: 8 consolidated rows, all single-voice medium or low, no CRITICAL or HIGH; the six cycle 1 rework findings are resolved

**Choice**: converged; R1 deferred to batch end (coordinator reproduced it); R2 discarded as refuted by a probe against the pre-rework source; R3 to R8 discarded to the ledger; no tail sweep (no row has two voices)

**Rationale**: phase-review rule: a single-voice medium or low row never becomes a task; R1 is deferred and not discarded because the defect reproduces in a scratch vault and bim tx validate reports the malformed note clean

### [deferred] 2026-11-23T21:59:42Z

**Decision**: `bim tx new` with a non-concept note (no --concept-type) skips all validation because the note classifies as plain. A multi-line title such as "a\n---\n# b" is written as a malformed note: the title is a quoted multi-line scalar, and the body is "# A", "---", "# b", so the `---` line later parses as the backmatter separator. The draft-validate guard only protects concept, index and run notes.

**Choice**: deferred

**Rationale**: deferred by review-close
