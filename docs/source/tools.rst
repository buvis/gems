CLI Tools
=========

Installation
------------

The base install registers all 9 CLIs but only pulls core dependencies.
Tools that need extra packages will tell you what to install if the dep is missing.

.. code-block:: bash

    uv tool install buvis-gems              # core CLIs
    uv tool install buvis-gems[bim]         # + jira
    uv tool install buvis-gems[bim,muc]     # combine extras
    uv tool install buvis-gems[all]         # everything

Available extras: ``bim``, ``hello-world``, ``muc``, ``pinger``, ``readerctl``, ``ml``, ``all``.

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
   * - :doc:`hello-world <tools/hello-world>`
     - ``hello-world``
     - Sample script template
   * - :doc:`muc <tools/muc>`
     -
     - Music collection tools (transcoding, tidying)
   * - :doc:`outlookctl <tools/outlookctl>`
     -
     - Outlook calendar CLI (Windows)
   * - :doc:`pinger <tools/pinger>`
     - ``pinger``
     - ICMP ping utilities
   * - :doc:`readerctl <tools/readerctl>`
     - ``readerctl``
     - Readwise Reader CLI
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
   tools/hello-world
   tools/muc
   tools/outlookctl
   tools/pinger
   tools/readerctl
   tools/zseq
