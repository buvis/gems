Filesystem
==========

Utilities for file metadata operations.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

`FileMetadataReader` is a static utility class under
`buvis.pybase.filesystem`. It surfaces creation and first-commit datetimes
with platform-aware fallbacks. No instantiation is required.

Quick Start
-----------

.. code-block:: python

    from pathlib import Path
    from buvis.pybase.filesystem import FileMetadataReader

    project_root = Path(__file__).resolve().parent

    creation_dt = FileMetadataReader.get_creation_datetime(project_root / "pyproject.toml")
    first_commit = FileMetadataReader.get_first_commit_datetime(project_root / "pyproject.toml")

    print(creation_dt, first_commit)

API Reference
-------------

FileMetadataReader
~~~~~~~~~~~~~~~~~~

.. autoclass:: buvis.pybase.filesystem.FileMetadataReader
   :members:
   :undoc-members:
   :show-inheritance:

Examples
--------

FileMetadataReader Example
~~~~~~~~~~~~~~~~~~~~~~~~~~

`FileMetadataReader` can guard metadata-dependent builds while accounting for
non-git working trees.

.. code-block:: python

    from pathlib import Path
    from buvis.pybase.filesystem import FileMetadataReader

    project_root = Path(__file__).resolve().parent
    config_file = project_root / "pyproject.toml"

    created = FileMetadataReader.get_creation_datetime(config_file)
    print(f"{config_file.name} born at {created.isoformat()}")

    first_commit = FileMetadataReader.get_first_commit_datetime(config_file)
    if first_commit is None:
        raise RuntimeError(
            f"{config_file} lives outside a Git repository; commit metadata unavailable."
        )
    print(f"First commit touching {config_file.name} occurred on {first_commit.date()}")
