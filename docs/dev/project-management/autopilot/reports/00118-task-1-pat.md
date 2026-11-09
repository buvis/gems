# Task 1 per-task review

## Initial

MEDIUM | src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py:21 | The contract says a non-datetime date raises `ValueError("Invalid date format")`. The old `.astimezone()` call rejected a plain `datetime.date`, because `date` has no `astimezone`. The new bare `.strftime("%Y%m%d%H%M%S")` accepts it. A date-only value such as YAML `date: 2024-09-13` now silently gets id `20240913000000` with fabricated `000000` time digits instead of raising. No test covers a `datetime.date` input. | Add `if not isinstance(date, datetime): raise ValueError("Invalid date format")` before formatting, then add a `datetime.date(2024, 9, 13)` case to `test_raises_on_invalid_date`.

LOW | tests/lib/zettel/entities/zettel/fixers/test_set_default_date.py:30 | The test saves `TZ`, restores it by hand in `finally`, and also uses `monkeypatch.setenv`. Monkeypatch already restores the env var at teardown, so the manual restore duplicates it and adds branching. | Put the TZ setup in a small fixture that calls `monkeypatch.setenv("TZ", ...)` and `time.tzset()`. Have it yield, then call `monkeypatch.undo()` and `time.tzset()`, or call `tzset` again after teardown. Drop the `original_timezone` bookkeeping and the try/finally.


## Delta (invalid contract; retained)

MEDIUM date-only rejection: resolved in code. The new `isinstance(zettel_data.metadata["date"], datetime)` guard at `set_default_id.py:22` raises `ValueError("Invalid date format")` before `strftime`. A `datetime.date` is not a `datetime` instance, so it now raises. The regression test I asked for is still missing, so I'm re-emitting that part.

LOW timezone cleanup: your rejection holds, because `tzset` has to be called again to restore libc state. I'm dropping it.

MEDIUM | src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py:22 | The new `isinstance` guard has no test. The delta changes no tests, so `test_raises_on_invalid_date` does not cover a `datetime.date` input. Removing the guard would let `date: 2024-09-13` silently get id `20240913000000`, and no test would fail. This is a bug fix, and `rules/testing.md` requires a regression test with it. | Add a `datetime.date(2024, 9, 13)` case to `test_raises_on_invalid_date`, asserting `ValueError("Invalid date format")`. Confirm it fails with the guard removed.

LOW | src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py:25 | The guard makes the `except AttributeError` around `.strftime` unreachable for `metadata["date"]`, since the guard guarantees a `datetime`. This change orphaned that handler. | Remove the `try/except AttributeError` and call `strftime` directly. Keep any other handler in the block that is still reachable.


## Corrected output

LOW | src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py:25 | The new `isinstance(..., datetime)` guard makes the `except AttributeError` handler almost unreachable. It now only fires if a datetime subclass's `strftime` raises `AttributeError`, so the code has two paths to the same `ValueError("Invalid date format")`. | Drop the `try/except AttributeError` around `strftime` and keep only the `isinstance` guard and the numeric-conversion handler. This would alter behavior for such subclasses, so make the call at PRD review.

LOW | tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py:11 | The parametrized argument `date` shadows the module-level `from datetime import date` import, which the `date-only` param still needs. That makes the file easy to misread. | Rename the test argument to `value` or `moment`.

LOW | tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py:12 | The task named the tests `id_keeps_the_dates_own_offset` and `date_defaults_to_local_offset`. The new tests have different names (`test_sets_id_from_dates_own_wall_clock`, `test_sets_local_date_without_microseconds`), so the contract names can't be found by grep. | Rename the tests to the contract names, or name the contract rule in each test's docstring or param ids.
