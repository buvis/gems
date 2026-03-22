CLI Tools
=========

Installation
------------

The base install registers all 16 CLIs but only pulls core dependencies.
Tools that need extra packages will tell you what to install if the dep is missing.

.. code-block:: bash

    uv tool install buvis-gems              # core CLIs
    uv tool install buvis-gems[bim]         # + jira
    uv tool install buvis-gems[bim,muc]     # combine extras
    uv tool install buvis-gems[all]         # everything

Available extras: ``bim``, ``bim-web``, ``fren``, ``hello-world``, ``morph``, ``muc``, ``pidash``, ``pinger``, ``readerctl``, ``all``.

Overview
--------

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Command
     - Extra
     - Description
   * - :doc:`bim <tools/bim>`
     - ``bim``
     - BUVIS InfoMesh — Zettelkasten management with Jira integration
   * - :doc:`dot <tools/dot>`
     -
     - Dotfiles manager
   * - :doc:`fctracker <tools/fctracker>`
     -
     - Foreign currency account tracker
   * - :doc:`fren <tools/fren>`
     - ``fren``
     - File renamer toolkit
   * - :doc:`hello-world <tools/hello-world>`
     - ``hello-world``
     - Sample script template
   * - :doc:`morph <tools/morph>`
     - ``morph``
     - File conversion toolkit
   * - :doc:`muc <tools/muc>`
     -
     - Music collection tools (transcoding, tidying)
   * - :doc:`netscan <tools/netscan>`
     -
     - Network scanning tools
   * - :doc:`outlookctl <tools/outlookctl>`
     -
     - Outlook calendar CLI (Windows)
   * - :doc:`pidash <tools/pidash>`
     - ``pidash``
     - Autopilot PRD cycle dashboard (TUI)
   * - :doc:`pinger <tools/pinger>`
     - ``pinger``
     - ICMP ping utilities
   * - :doc:`puc <tools/puc>`
     -
     - Photo utility collection
   * - :doc:`readerctl <tools/readerctl>`
     - ``readerctl``
     - Readwise Reader CLI
   * - :doc:`sysup <tools/sysup>`
     -
     - System update tools
   * - :doc:`vuc <tools/vuc>`
     -
     - Video utility collection
   * - :doc:`zseq <tools/zseq>`
     -
     - Zettelsequence file naming utilities

Common Options
--------------

Every tool inherits these options from the shared ``buvis_options`` decorator:

.. code-block:: text

    --config FILE                   YAML config file path
    --config-create FILE            Generate YAML config template to FILE
    --config-dir DIRECTORY          Configuration directory
    --log-level [debug|info|warning|error]
    --debug / --no-debug            Enable debug mode

See :doc:`configuration` for how settings are resolved (CLI > env > YAML > defaults).

Extending Tools
---------------

Each tool follows the same Click-based pattern:

.. code-block:: python

    import click
    from buvis.pybase.configuration import buvis_options, get_settings

    @click.command()
    @buvis_options
    @click.pass_context
    def cli(ctx: click.Context) -> None:
        settings = get_settings(ctx)
        command = MyCommand(settings)
        command.execute()

See :doc:`configuration` for how to create custom settings classes and YAML config files.

.. toctree::
   :maxdepth: 1
   :caption: Tool Reference:
   :hidden:

   tools/bim
   tools/dot
   tools/fctracker
   tools/fren
   tools/hello-world
   tools/morph
   tools/muc
   tools/netscan
   tools/outlookctl
   tools/pidash
   tools/pinger
   tools/puc
   tools/readerctl
   tools/sysup
   tools/vuc
   tools/zseq
