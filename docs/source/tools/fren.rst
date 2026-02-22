.. _tool-fren:

fren
====

File renamer toolkit. Slugify, directorize, flatten, and normalize filenames.

**Extra:** ``uv tool install buvis-gems[fren]``

Commands
--------

fren slug
~~~~~~~~~

Slugify filenames — convert to URL-safe lowercase with hyphens.

.. code-block:: bash

    fren slug file1.txt file2.txt
    fren slug *.pdf

fren directorize
~~~~~~~~~~~~~~~~

Wrap each file in a directory named after the file stem.

.. code-block:: bash

    fren directorize ~/downloads/

fren flatten
~~~~~~~~~~~~

Copy nested files into a flat destination directory.

.. code-block:: bash

    fren flatten ~/nested-dir/ ~/flat-output/

fren normalize
~~~~~~~~~~~~~~

NFC-normalize directory names (Unicode normalization).

.. code-block:: bash

    fren normalize ~/documents/
