buvis-gems Documentation
========================

Python toolkit and CLI tools for BUVIS. Provides configuration management,
filesystem utilities, adapters for external tools, string formatting, and
the zettel subsystem for Zettelkasten management.

Getting Started
---------------

**Configuration** is the recommended entry point. It defines how your tools load
settings from CLI arguments, environment variables, YAML files, and defaults.

Quick Example
~~~~~~~~~~~~~

.. code-block:: python

    import click
    from buvis.pybase.configuration import buvis_options, get_settings

    @click.command()
    @buvis_options
    @click.pass_context
    def main(ctx: click.Context) -> None:
        settings = get_settings(ctx)
        if settings.debug:
            click.echo("Debug mode")

See :doc:`configuration` for custom settings classes, YAML configuration,
environment variables, and migration guides.

.. toctree::
   :maxdepth: 2
   :caption: Library:

   configuration
   formatting
   filesystem
   adapters
   zettel

.. toctree::
   :maxdepth: 2
   :caption: CLI Tools:

   tools
