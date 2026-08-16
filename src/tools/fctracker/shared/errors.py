"""Shared error translation for fctracker's transaction-reading commands."""

from __future__ import annotations

import queue
from decimal import DivisionUndefined, InvalidOperation


def describe_transaction_error(account_name: str, exc: Exception) -> str:
    """Translate a transaction-reading failure into a message naming the account.

    `queue.Empty` stringifies to an empty string and `decimal.InvalidOperation`
    stringifies to a bare class repr (e.g. "[<class 'decimal.ConversionSyntax'>]"),
    so both are given a fixed, human-readable cause instead of interpolating
    `str(exc)` directly. `InvalidOperation` covers two distinct signals -
    malformed input (`ConversionSyntax`) and division by a zero amount
    (`DivisionUndefined`) - distinguished via `exc.args[0]`, the list of
    decimal condition classes that fired.

    Args:
        account_name: name of the account being processed.
        exc: the exception raised by `TransactionsReader.get_transactions()`.

    Returns:
        An error message naming the account and a meaningful cause.
    """
    if isinstance(exc, queue.Empty):
        cause = "account is overdrawn"
    elif isinstance(exc, InvalidOperation):
        conditions = exc.args[0] if exc.args else []
        if DivisionUndefined in conditions:
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
