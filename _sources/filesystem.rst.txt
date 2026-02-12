Filesystem
==========

Utilities for directory traversal, file metadata, and batch operations.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

`DirTree` and `FileMetadataReader` are static utility classes under
`buvis.pybase.filesystem`. Each exposes class-level helpers—no
instantiation is required—to inspect directory depth, prune files, or read
timestamps. DirTree bundles cleanup routines (counting files, normalizing
extensions, removing empty folders, and merging Mac metadata), while
FileMetadataReader surfaces creation and first-commit datetimes with
platform-aware fallbacks.

Quick Start
-----------

.. code-block:: python

    from pathlib import Path
    from buvis.pybase.filesystem import DirTree, FileMetadataReader

    project_root = Path(__file__).resolve().parent

    # Static utilities: no DirTree() or FileMetadataReader() instantiation.
    total_files = DirTree.count_files(project_root / "src")
    creation_dt = FileMetadataReader.get_creation_datetime(project_root / "pyproject.toml")
    first_commit = FileMetadataReader.get_first_commit_datetime(project_root / "pyproject.toml")

    print(total_files, creation_dt, first_commit)

API Reference
-------------

DirTree
~~~~~~~

.. autoclass:: buvis.pybase.filesystem.DirTree
   :members:
   :undoc-members:
   :show-inheritance:

FileMetadataReader
~~~~~~~~~~~~~~~~~~

.. autoclass:: buvis.pybase.filesystem.FileMetadataReader
   :members:
   :undoc-members:
   :show-inheritance:

Examples
--------

DirTree Example
~~~~~~~~~~~~~~~

Use `DirTree` to profile and clean a release artifact directory before publishing.

.. code-block:: python

    from pathlib import Path
    from buvis.pybase.filesystem import DirTree

    project_root = Path(__file__).resolve().parent
    artifacts_dir = project_root / "dist" / "artifacts"

    file_count = DirTree.count_files(artifacts_dir)
    max_depth = DirTree.get_max_depth(artifacts_dir)
    print(f"Artifact tree: {file_count} files across {max_depth} levels.")

    DirTree.delete_by_extension(artifacts_dir, [".tmp", ".log"])
    DirTree.normalize_file_extensions(artifacts_dir)
    DirTree.remove_empty_directories(artifacts_dir)
    DirTree.merge_mac_metadata(artifacts_dir)

    # The cleanup routine removes stray caches, coerces extensions to the
    # project standard, prunes empty folders, and restores macOS metadata.

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
