Development
===========

Setup
-----

.. code-block:: bash

    uv sync --all-groups --all-extras
    pre-commit install
    uv run pytest
    uv run mypy src/lib/ src/tools/

Release
-------

.. code-block:: bash

    release patch|minor|major              # bump, tag, push → CI publishes to PyPI
    release --pre rc1                      # pre-release current version to TestPyPI
    release --pre rc1 minor                # bump + pre-release to TestPyPI
    release                                # after rc: strip suffix, release stable to PyPI

``mise`` adds ``dev/bin`` to PATH. Tags with ``rc`` publish to TestPyPI; stable tags go to PyPI.
