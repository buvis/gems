Permission deny rule (/Users/bob/.claude/settings.json): Write(**/dev/local/**) is not matched by file permission checks — only Edit(path) rules are. Use Edit(**/dev/local/**) instead (Edit rules cover all file-editing tools).
The Python fallback now restarts progress at "archiving" after a post-close failure. The new test file `tests/tools/backup/test_tar_fallback_progress.py` passes: 8 passed, exit 0. I ran only that file.

- **Fallback restart:** when system-tar fails after finalizing, the fallback now builds fresh progress callbacks before the Python rewrite, so the activity sequence goes archiving, finalizing, archiving, finalizing.
- **Rename:** `_archive_callbacks` is now `_start_archive_progress`, with the same callback shape and throttle.
- **Changelog:** one Unreleased "Fixed" entry covers the fallback phase.

The restart also fires when system-tar fails before it finalizes (for example a nonzero tar exit), not only after close. That adds one extra "archiving" event in that case. The tests don't cover it.

ASSUMPTIONS:
- The fallback restarts progress with the same engine string, so `done_bytes` stays None, as the test requires.
- The extra "archiving" event on pre-finalize fallback is acceptable.

FILES_TOUCHED:
src/tools/backup/capabilities/tar_archive.py
CHANGELOG.md
