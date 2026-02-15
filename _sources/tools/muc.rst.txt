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

.. code-block:: bash

    muc tidy ~/music/album/
    muc tidy ~/music/album/ -y     # skip confirmation

Options:

- ``-y, --yes`` — skip confirmation prompt
