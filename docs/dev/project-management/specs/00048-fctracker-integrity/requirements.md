# fctracker: validate CSV order and handle bad/overdraft rows

<!-- requirements; migrated from PRD 00048 flat file -->

## Problem

fctracker reports wrong money on a normally-ordered ledger, silently. The FIFO cost-basis computation assumes the CSV is newest-first: `rows.insert(0, row)` (`src/tools/fctracker/adapters/transactions/transactions_reader.py:27-28`) reverses the file into oldest-first, with **no validation** that the input was actually newest-first. A user who appends new rows at the end of the file (the natural way to keep a ledger) gets the rows processed in the wrong order, so withdrawals consume the wrong deposit lots and the reported local cost/rate is wrong — with no error. The convention isn't even documented (`docs/source/tools/fctracker.rst` never mentions "csv"). Separately, error rows crash with raw tracebacks: overdraft raises `queue.Empty` (`domain/quantified_queue.py:32`), a zero-amount row raises `DivisionUndefined` (`domain/account.py:42`), a malformed cell raises `InvalidOperation` (`transactions_reader.py:31`), and the command layer catches only `FileNotFoundError` (`commands/transactions/transactions.py:48-52`).

## Solution

After the reversal, assert the dates are non-decreasing (oldest-first); if not, fail loud with a clear message naming the expected order. Catch the overdraft/zero-amount/malformed-cell errors in the command layer and return `CommandResult(success=False, error=...)` with a human message. Document the CSV order in the tool docs.

## Requirements

### Must have
- After reversing, fctracker verifies dates are monotonically non-decreasing; on violation it returns `CommandResult(success=False, error="transactions must be newest-first; row N breaks order")` (or equivalent) instead of computing wrong numbers.
- Overdraft (`queue.Empty`), zero-amount division, and malformed-cell (`InvalidOperation`) are caught in the command layer → `CommandResult(success=False, error=...)` with a message naming the account/row; no raw traceback reaches the user.
- Regression tests: (a) a mis-ordered CSV is rejected with a clear error; (b) an overdrawn account returns a friendly error, not `queue.Empty`; (c) a malformed amount cell returns a friendly error.
- The Decimal end-to-end arithmetic is preserved (do not introduce float).

### Nice to have
- Document the expected CSV order in `docs/source/tools/fctracker.rst`.

## Success Criteria

- A chronologically-appended ledger is either processed correctly or rejected with a clear message — never silently miscomputed.
- No raw traceback from fctracker; Decimal math intact; fctracker tests green.
