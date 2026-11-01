"""Shared error translation for fctracker's transaction-reading commands."""

from __future__ import annotations

import queue
from decimal import DivisionUndefined, InvalidOperation

# The messages `_pydecimal` raises `DivisionUndefined` with (see `_division_undefined`).
_PYDECIMAL_DIVISION_UNDEFINED = frozenset({"0 / 0", "0 // 0", "0 % 0", "divmod(0, 0)", "remainder_near(0, 0)"})


def _division_undefined(exc: InvalidOperation) -> bool:
    """Whether `exc` is a decimal 0/0 (`DivisionUndefined`) rather than e.g. malformed input.

    The C `_decimal` module raises `InvalidOperation` with the list of fired
    condition classes in `args[0]`. The pure-Python fallback (`_pydecimal`, which
    CPython uses when built without libmpdec, as the actions/setup-python 3.15
    builds are) maps the condition to plain `InvalidOperation` and keeps only a
    message, so that is matched instead.
    """
    fired = exc.args[0] if exc.args else None
    if isinstance(fired, list):
        return DivisionUndefined in fired
    return isinstance(exc, DivisionUndefined) or fired in _PYDECIMAL_DIVISION_UNDEFINED


def describe_transaction_error(account_name: str, exc: Exception) -> str:
    """Translate a transaction-reading failure into a message naming the account.

    `queue.Empty` stringifies to an empty string and `decimal.InvalidOperation`
    stringifies to a bare class repr (e.g. "[<class 'decimal.ConversionSyntax'>]"),
    so both are given a fixed, human-readable cause instead of interpolating
    `str(exc)` directly. `InvalidOperation` covers two distinct signals -
    malformed input (`ConversionSyntax`) and division by a zero amount
    (`DivisionUndefined`) - told apart by `_division_undefined`.

    Args:
        account_name: name of the account being processed.
        exc: the exception raised by `TransactionsReader.get_transactions()`.

    Returns:
        An error message naming the account and a meaningful cause.
    """
    if isinstance(exc, queue.Empty):
        cause = "account is overdrawn"
    elif isinstance(exc, InvalidOperation):
        if _division_undefined(exc):
            # TransactionsReader now rejects a zero amount with a ValueError
            # before Account.withdraw() can divide by it, so this branch is
            # unreachable from that call site. Kept as defense-in-depth for
            # any other caller of Account.withdraw()/deposit().
            cause = "transaction amount is zero"
        else:
            cause = "malformed or undefined transaction amount"
    else:
        cause = str(exc)
    return f"error processing transactions for account '{account_name}': {cause}"
