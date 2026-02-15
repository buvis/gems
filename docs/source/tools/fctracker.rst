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
