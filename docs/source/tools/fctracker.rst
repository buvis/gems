.. _tool-fctracker:

fctracker
=========

Track balances and transactions across foreign currency accounts.

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``transactions_dir``
     - ``""``
     - Directory containing transaction files
   * - ``local_currency``
     - ``code=CZK, symbol=Kč, precision=2``
     - Local currency config
   * - ``foreign_currencies``
     - ``{}``
     - Map of currency code to ``{symbol, precision}``

Example YAML config:

.. code-block:: yaml

    transactions_dir: ~/finance/transactions
    local_currency:
      code: CZK
      symbol: "Kč"
      precision: 2
    foreign_currencies:
      EUR:
        symbol: "€"
        precision: 2
      USD:
        symbol: "$"
        precision: 2

Transaction files
-----------------

Each account/currency pair is one CSV under ``transactions_dir``, named
``<account>/<currency>.csv`` in lower case — for example
``~/finance/transactions/savings/eur.csv``.

The file has four columns: ``date``, ``amount``, ``rate``, ``description``.
Dates are ``YYYY-MM-DD``. A positive ``amount`` is a deposit and needs a
``rate``; a negative ``amount`` is a withdrawal, whose rate is derived from the
deposits it consumes. An amount of zero is rejected.

**Rows must be newest first.** The newest transaction goes at the TOP of the
file, directly under the header, and the oldest at the bottom:

.. code-block:: text

    date,amount,rate,description
    2024-03-01,-50.00,,Amazon purchase
    2024-02-01,200.00,25.10,
    2024-01-15,100.00,25.50,

This order is not cosmetic. fctracker matches withdrawals against deposits
first-in-first-out to compute cost basis, so reading the rows in the wrong order
would consume the wrong deposits and report wrong local cost and rates.

If the dates are not newest-first, the command fails with an error naming the
file and the offending row, for example::

    transactions must be newest-first; data row 4 breaks order

Row numbers count data rows only — the header is not row 1. Nothing is computed
when a file is rejected, so a mis-ordered ledger can never produce wrong numbers.

Appending new transactions to the END of the file is therefore rejected rather
than silently miscomputed. Add new rows at the top instead.

Files are read as UTF-8; a byte-order mark, which spreadsheets often add on
export, is accepted.

Commands
--------

fctracker balance
~~~~~~~~~~~~~~~~~

Print current balance across all accounts and currencies.

.. code-block:: bash

    fctracker balance

fctracker transactions
~~~~~~~~~~~~~~~~~~~~~~

Print transaction ledger with optional filters.

.. code-block:: bash

    fctracker transactions
    fctracker transactions -a savings -c EUR
    fctracker transactions -m 2025-01

Options:

- ``-a, --account TEXT`` — filter by account
- ``-c, --currency TEXT`` — filter by currency
- ``-m, --month TEXT`` — filter by month (``YYYY-MM``)
