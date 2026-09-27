Formatting
==========

The formatting helpers centralize string manipulation so your tools can produce
consistent field names and human-friendly labels.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

`StringOperator` exposes casing helpers and abbreviation handling that bundle
common rules for note fields and titles:

- **Case conversion** covers camelCase and snake_case plus note-field
  (kebab-case) normalization for display labels and metadata keys.
- **Abbreviation expansion** lets you replace short forms with full phrases or
  abbreviations sourced from config or code.
- **Whitespace helpers** collapse and shorten text for compact display.

Quick Start
-----------

.. code-block:: python

    from buvis.pybase.formatting import StringOperator

    field = StringOperator.as_note_field_name("BUVIS CLI Utilities")
    camel = StringOperator.camelize("cli_utilities")

    print(field)  # => "buvis-cli-utilities"
    print(camel)  # => "CliUtilities"

API Reference
-------------

.. autoclass:: buvis.pybase.formatting.StringOperator
   :members:
   :undoc-members:
   :show-inheritance:

Helper Classes
--------------

.. autoclass:: buvis.pybase.formatting.string_operator.string_case_tools.StringCaseTools
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: buvis.pybase.formatting.string_operator.abbr.Abbr
   :members:
   :undoc-members:
   :show-inheritance:
