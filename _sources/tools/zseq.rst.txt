.. _tool-zseq:

zseq
====

Work with Zettelkasten sequential file naming (``YYYYMMDDHHMMSS`` prefixes).
Reports the highest sequence number in a directory.

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``path_dir``
     - ``/Volumes/photography/photography/src/2024``
     - Directory to scan
   * - ``is_reporting_misnamed``
     - ``false``
     - Report files not following zettelseq naming

Commands
--------

.. code-block:: bash

    zseq                                 # max seq in default dir
    zseq -p ~/photos/2025/               # custom directory
    zseq -m                              # also report misnamed files

Options:

- ``-p, --path TEXT`` — directory to scan
- ``-m, --misnamed-reporting`` — report non-conforming files
