"""Shared error translation for fctracker's transaction-reading commands."""

from __future__ import annotations

import queue
from decimal import InvalidOperation


def describe_transaction_error(account_name: str, exc: Exception) -> str:
    """Translate a transaction-reading failure into a message naming the account.

    `queue.Empty` stringifies to an empty string and `decimal.InvalidOperation`
    stringifies to a bare class repr (e.g. "[<class 'decimal.ConversionSyntax'>]"),
    so both are given a fixed, human-readable cause instead of interpolating
    `str(exc)` directly.

    Args:
        account_name: name of the account being processed.
        exc: the exception raised by `TransactionsReader.get_transactions()`.

    Returns:
        An error message naming the account and a meaningful cause.
    """
    if isinstance(exc, queue.Empty):
        cause = "account is overdrawn"
    elif isinstance(exc, InvalidOperation):
        cause = "malformed or undefined transaction amount"
    else:
        cause = str(exc)
    return f"error processing transactions for account '{account_name}': {cause}"
