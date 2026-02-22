.. _tool-puc:

puc
===

Photo utility collection. Strip EXIF metadata while preserving copyright and dates.

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``strip_keep_tags``
     - ``DateTimeOriginal``, ``CreateDate``, ``ModifyDate``, ``Copyright``, ``XMP-dc:Rights``, ``IPTC:CopyrightNotice``
     - EXIF tags to preserve during strip

Commands
--------

puc strip
~~~~~~~~~

Strip EXIF metadata from photos, keeping copyright and date tags.

.. code-block:: bash

    puc strip photo.jpg
    puc strip *.jpg
