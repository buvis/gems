Permission deny rule (/Users/bob/.claude/settings.json): Write(**/dev/local/**) is not matched by file permission checks — only Edit(path) rules are. Use Edit(**/dev/local/**) instead (Edit rules cover all file-editing tools).
Both test files now pass (143 passed): the new `test_tar_fallback_progress.py` and the existing `test_progress.py`. I did not run the full suite, as instructed.

`test_progress.py` was failing. The fallback always restarted the `archiving` event, which added an extra one when `tar` was missing. I fixed that in `src/tools/backup/capabilities/tar_archive.py`. The fallback now restarts `archiving` only if system tar reached `finalizing`, tracked by a small wrapper around `on_finalize`.

The `_start_archive_progress` rename and the Unreleased Fixed changelog entry were already in place, so I left them alone.

ASSUMPTIONS: none
FILES_TOUCHED:
src/tools/backup/capabilities/tar_archive.py
