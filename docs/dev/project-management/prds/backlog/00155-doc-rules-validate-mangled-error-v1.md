---
design: skip
default_model: sonnet
model_tier_rationale: Two call sites get one named helper; every check fails loudly.
---
# `bim doc rules validate` shows a mangled error for a malformed `issuers.yml`

Source: agoge run 2026-11-23, finding 15 of 21 (LOW, verified, lane wendy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

`bim doc rules validate` prints the command's error text as console markup. Rich reads a square-bracketed part as a style tag and drops it. For a malformed `issuers.yml` the YAML error loses the text from `[unclosed` to `']'`, so the user sees a broken message for exactly the error the command exists to report.

`bim doc rules test` has the same shape: it passes `result.error` straight to `console.panic`. The lane did not run it.

Both calls are in `src/tools/bim/doc_rules_cli.py`. The other `bim doc` failures do not have the problem: `_DocGroup.invoke` in `src/tools/bim/doc_cli.py` escapes its message.

## Solution

Escape the message at the two direct `console.panic` calls with `rich.markup.escape`. This is the helper `_DocGroup.invoke` already uses (`from rich.markup import escape`, then `console.panic(escape(str(exc)))`).

In `src/tools/bim/doc_rules_cli.py`:

- add `from rich.markup import escape` to the module imports;
- in `doc_rules_validate`: `console.panic(escape(result.error or "validate failed"))`;
- in `doc_rules_test`: `console.panic(escape(result.error or "rule test failed"))`.

Nothing else changes: the fallback texts, the ` ✘ ` marker, and exit code 1 stay the same. The other `console.panic` calls in the file take fixed text or a path and are out of scope.

## Requirements

### Must have
- `bim doc rules validate` on an `issuers.yml` holding `issuers: [unclosed` exits 1 and its output, with line breaks removed, contains `[unclosed`.
- `bim doc rules test` with a failed result whose error is `clause [amount] did not match` exits 1 and its output contains `clause [amount] did not match`.
- `src/tools/bim/doc_rules_cli.py` holds exactly two `console.panic(escape(` calls.
- `CHANGELOG.md` gains this line under `[Unreleased]` / `### Fixed`: `- **bim**: \`bim doc rules validate\` and \`bim doc rules test\` now print an error that contains square brackets in full. Before, the bracketed part of a YAML error for a malformed \`issuers.yml\` was dropped.`

### Nice to have
- None.

## Implementation

### Module: doc rules literal panic
- **Location**: `src/tools/bim/doc_rules_cli.py`, `tests/tools/bim/doc/test_doc_rules_cli_exit_code.py`, `CHANGELOG.md`
- **Responsibility**: print `rules validate` and `rules test` failure text literally
- **Exports**: none
- New symbols: `TestDocRulesPanicTextIsLiteral`, `test_validate_shows_the_bracketed_part_of_a_yaml_error`, `test_rules_test_shows_square_brackets_in_the_failure_body`
- **Risk**: This is one more per-call-site patch. If finding 6 of the same run later makes console output literal by default, these two `escape` calls would double-escape and must be removed in that change. A message that used markup on purpose would now print its tags; neither command class emits markup. No existing test pins the mangled output: `TestUnusableIssuersFile` in `tests/tools/bim/doc/test_doc_rules_cli_exit_code.py` does not run `rules validate`, and its `rules test` cases fail earlier, in `_DocGroup.invoke`.

### Dependencies
- doc rules literal panic: No dependencies (foundation)

## Test Strategy

Both tests go in `tests/tools/bim/doc/test_doc_rules_cli_exit_code.py`, in a new class `TestDocRulesPanicTextIsLiteral`. They use the file's `_bim_settings_with_doc(tmp_path)` helper and patch `bim.doc_rules_cli.get_settings`.

- `test_validate_shows_the_bracketed_part_of_a_yaml_error`: write `issuers: [unclosed` to `tmp_path / "issuers.yml"`, run `bim doc rules validate` with the real `CommandRulesValidate`. Assert exit code 1 and `"[unclosed" in result.output.replace("\n", "")`.
- `test_rules_test_shows_square_brackets_in_the_failure_body`: write a small file to `tmp_path / "input.pdf"`; patch `bim.dependencies.get_issuer_registry` and `bim.dependencies.get_ocr_runner` with mocks, and `bim.commands.doc.rules.test.CommandRulesTest` to return an object whose `run` gives `CommandResult(success=False, error="clause [amount] did not match")`, as the list and backtest tests in the same file do. Run `bim doc rules test probe --pdf <input.pdf>`. Assert exit code 1 and the full error text in the output.

Evidence status: the `rules validate` half is verified live. The lane did not run the `rules test` half; it has the same code shape, and the second test is its first check.

Evidence from the report, verbatim:

```
**Evidence** (confirmed). `issuers: [unclosed`: `bim doc rules list` prints the full error;
`bim doc rules validate` prints `issuers: ', but got '<stream end>'`, with the text from
`[unclosed` to `']'` missing, rc 1.
```

## Tasks

### Phase 0: Fix
- [ ] Add class `TestDocRulesPanicTextIsLiteral` with `test_validate_shows_the_bracketed_part_of_a_yaml_error` and `test_rules_test_shows_square_brackets_in_the_failure_body` to `tests/tools/bim/doc/test_doc_rules_cli_exit_code.py`; watch them fail - Acceptance: `uv run pytest tests/tools/bim/doc/test_doc_rules_cli_exit_code.py -k TestDocRulesPanicTextIsLiteral` fails on the unmodified code.
- [ ] Import `escape` from `rich.markup` in `src/tools/bim/doc_rules_cli.py` and wrap the two `console.panic(result.error or ...)` messages (depends on: previous task) - Acceptance: `uv run pytest tests/tools/bim/doc/test_doc_rules_cli_exit_code.py` passes and `rg -c "console\.panic\(escape\(" src/tools/bim/doc_rules_cli.py` prints `2`.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` under `[Unreleased]` (depends on: previous task) - Acceptance: `rg -n "contains square brackets in full" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest tests/tools/bim/doc/test_doc_rules_cli_exit_code.py` passes; the project's full test gate (`uv run pytest`) passes.
