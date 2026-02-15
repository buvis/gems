.. _tool-readerctl:

readerctl
=========

CLI for Readwise Reader. Add URLs to your reading list.

**Extra:** ``uv tool install buvis-gems[readerctl]``

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``token_file``
     - ``~/.config/scripts/readwise-token``
     - Path to API token file

Commands
--------

readerctl login
~~~~~~~~~~~~~~~

Authenticate with Readwise. Prompts for token and stores it.

.. code-block:: bash

    readerctl login

readerctl add
~~~~~~~~~~~~~

Add URL(s) to Reader. Requires prior ``login``.

.. code-block:: bash

    readerctl add -u https://example.com/article
    readerctl add -f ~/urls.txt     # one URL per line

Options:

- ``-u, --url TEXT`` — single URL to add
- ``-f, --file TEXT`` — file with URLs (one per line)
