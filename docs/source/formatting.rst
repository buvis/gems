Formatting
==========

The formatting helpers centralize string manipulation so your tools can produce
consistent slugs, human-friendly labels, and tag suggestions.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

`StringOperator` exposes slugification, casing helpers, and word-level
transformations that bundle common rules for mushtags and filenames:

- **Slugification** applies transliteration, delimiter normalization, and
  abbreviation handling to create URL-safe identifiers.
- **Case conversion** covers camelCase, snake_case, and title-case variants
  plus reversals for finetuning display labels.
- **Word operations** offer splitting, joining, and inflection helpers that
  respect existing abbreviations and brand-safe capitalizations.
- **Abbreviation expansion** lets you replace short forms with full phrases or
  abbreviations sourced from config or code.
- **Tag suggestion** helps derive consistent namespace/build tags from raw
  phrases or file paths.

Quick Start
-----------

.. code-block:: python

    from buvis.pybase.formatting import StringOperator

    slug = StringOperator.slugify("BUVIS-CLI Utilities")
    camel = StringOperator.camelize("cli_utilities")

    print(slug)   # => "buvis-cli-utilities"
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

.. autoclass:: buvis.pybase.formatting.string_operator.word_level_tools.WordLevelTools
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: buvis.pybase.formatting.string_operator.abbr.Abbr
   :members:
   :undoc-members:
   :show-inheritance:
