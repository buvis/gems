.. _tool-muc:

muc
===

Music collection tools for transcoding and cleanup.

**Extra:** ``uv tool install buvis-gems[muc]``

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``limit_flac_bitrate``
     - ``1411000``
     - Target bitrate (bps)
   * - ``limit_flac_bit_depth``
     - ``16``
     - Target bit depth
   * - ``limit_flac_sampling_rate``
     - ``44100``
     - Target sampling rate (Hz)
   * - ``tidy_junk_extensions``
     - ``.cue .db .jpg .lrc .m3u .md .nfo .png .sfv .txt .url``
     - File extensions to remove during tidy

Commands
--------

muc limit
~~~~~~~~~

Transcode FLAC files to target spec (CD quality by default).

.. code-block:: bash

    muc limit ~/music/hi-res-album/
    muc limit ~/music/hi-res-album/ -o ~/music/transcoded/

Options:

- ``-o, --output TEXT`` — output directory (default: ``./transcoded``)

muc tidy
~~~~~~~~

Clean up a music directory: merge macOS metadata, normalize extensions,
remove junk files, delete empty directories.

Reports every completed rename, metadata merge, file deletion and empty-directory
removal through the standard console. Filesystem failures and metadata files that
could not be merged produce warnings; tidy continues with the remaining items.
Warnings alone do not change the exit status (0). Each step's actions and
warnings print in the order the step ran. Programmatic callers get them in
``CommandResult.info`` and ``CommandResult.warnings``, and per step in
``CommandResult.metadata["steps"]``.

Tidy deletes files with the junk extensions (``tidy_junk_extensions``, which
include ``.txt``, ``.md``, ``.jpg`` and ``.png`` by default) without asking. It
asks for confirmation only when the tree holds more than 100 files or is deeper
than 3 levels. A metadata file (``._name``) whose data file is a symlink is
kept with a warning; tidy never writes metadata through a link.

.. code-block:: bash

    muc tidy ~/music/album/
    muc tidy ~/music/album/ -y     # skip the large-tree confirmation

Options:

- ``-y, --yes`` — skip the confirmation prompt for trees over 100 files or 3 levels deep
