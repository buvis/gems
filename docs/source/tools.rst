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

Tools
-----

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Command
     - Extra
     - Description
   * - ``bim``
     - ``bim``
     - BUVIS InfoMesh — Zettelkasten management with Jira integration
   * - ``dot``
     -
     - Dotfiles manager
   * - ``fctracker``
     -
     - Foreign currency account tracker
   * - ``hello-world``
     - ``hello-world``
     - Sample script template
   * - ``muc``
     - ``muc``
     - Music collection tools (tagging, tidying)
   * - ``outlookctl``
     -
     - Outlook calendar CLI (Windows)
   * - ``pinger``
     - ``pinger``
     - ICMP ping utilities
   * - ``readerctl``
     - ``readerctl``
     - Readwise Reader CLI
   * - ``zseq``
     -
     - Zettelsequence file naming utilities

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
