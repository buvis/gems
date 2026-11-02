# Devon 2 adversarial validation

Logical opus; actual OpenAI gpt-6.1-sol/high. Eight independent runnable mutants; eight successful exact-runner executions; no failed attempts. Tests unchanged; tar_archive.py restored byte-for-byte after every run; CHANGELOG.md untouched.

Command for each mutant: `uv run pytest tests/tools/backup/test_progress.py -k "engine or input_bytes or swallowed" -q --tb=line` (subprocess timeout 300 seconds).

## Temporary baseline changes

The supplied original source lacks progress handling. Each independent wrong implementation starts with the following shared progress wiring applied to the original source, then exactly one mutant diff below. This baseline was temporary and has been restored.

```diff
--- original/tar_archive.py
+++ temporary-baseline/tar_archive.py
@@ -7,6 +7,7 @@
 import subprocess
 import tarfile
 import tempfile
+import time
 from datetime import datetime
 from pathlib import Path
 from typing import TYPE_CHECKING, cast
@@ -16,11 +17,11 @@
     ExcludeState,
     state_for_directory,
 )
-from backup.step_result import ArchiveMeta, PlanEntry, StepResult
+from backup.step_result import ArchiveMeta, PlanEntry, ProgressEvent, StepResult
 
 if TYPE_CHECKING:
     import threading
-    from collections.abc import Iterable, Iterator, Mapping
+    from collections.abc import Callable, Iterable, Iterator, Mapping
 
 __all__ = ["ArchiveCancelled", "TarArchive", "WalkResult"]
 
@@ -31,6 +32,17 @@
 
 class ArchiveCancelled(Exception):
     """Archive creation stopped before publication."""
+
+
+def _emit_progress(
+    progress: Callable[[ProgressEvent], None] | None,
+    event: ProgressEvent,
+) -> None:
+    if progress is not None:
+        try:
+            progress(event)
+        except Exception:
+            pass
 
 
 def _check_cancel(cancel: threading.Event | None) -> None:
@@ -162,6 +174,7 @@
         cancel = cast("threading.Event | None", kwargs.get("cancel"))
         _check_cancel(cancel)
         dry_run = bool(kwargs.get("dry_run", False))
+        progress = None if dry_run else cast("Callable[[ProgressEvent], None] | None", kwargs.get("progress"))
         base_state = ExcludeState(base_excludes=frozenset(_as_str_tuple(kwargs.get("excludes", ()))))
         missing: list[str] = []
         bundle = "items" in kwargs
@@ -171,6 +184,7 @@
             except ValueError as exc:
                 yield StepResult(label, success=False, message=str(exc))
                 return
+            _emit_progress(progress, ProgressEvent(label, "scanning", None, None))
             walk, missing = _select_items(source, base_state, selected)
             _check_cancel(cancel)
             if not walk.files:
@@ -180,13 +194,14 @@
                 yield StepResult(label, success=True, message=message, skipped=True)
                 return
         else:
+            _emit_progress(progress, ProgressEvent(label, "scanning", None, None))
             walk = _walk_tree(source, base_state)
             _check_cancel(cancel)
 
         if dry_run:
             result = self._dry_run_result(label, out, walk)
         else:
-            result = self._archive_result(label, source if bundle else source.parent, out, walk, engine, cancel=cancel)
+            result = self._archive_result(label, source if bundle else source.parent, out, walk, engine, cancel=cancel, progress=progress)
         if missing:
             result.message += f"; missing items: {', '.join(missing)}"
         yield result
@@ -206,19 +221,43 @@
         )
 
     @staticmethod
-    def _archive_result(  # noqa: PLR0913 — retain archive context plus keyword-only cancellation
-        label: str, arcbase: Path, out: Path, walk: WalkResult, engine: str, *, cancel: threading.Event | None = None
+    def _archive_result(
+        label: str, arcbase: Path, out: Path, walk: WalkResult, engine: str, *,
+        cancel: threading.Event | None = None,
+        progress: Callable[[ProgressEvent], None] | None = None,
     ) -> StepResult:
         _check_cancel(cancel)
         out.parent.mkdir(parents=True, exist_ok=True)
         note = ""
+        latest = 0
+        reported = 0
+        last_time = time.monotonic()
+        is_python = engine == _ENGINE_PYTHON
+        _emit_progress(progress, ProgressEvent(label, "archiving", 0 if is_python else None, walk.total_bytes))
+
+        def on_bytes(done: int) -> None:
+            nonlocal latest, reported, last_time
+            latest = done
+            now = time.monotonic()
+            if now - last_time >= 0.2:
+                _emit_progress(progress, ProgressEvent(label, "archiving", latest, walk.total_bytes))
+                reported = latest
+                last_time = now
+
+        def finalize() -> None:
+            nonlocal reported
+            if is_python and latest != reported:
+                _emit_progress(progress, ProgressEvent(label, "archiving", latest, walk.total_bytes))
+                reported = latest
+            _emit_progress(progress, ProgressEvent(label, "finalizing", latest if is_python else None, walk.total_bytes))
+
         if engine == _ENGINE_SYSTEM_TAR:
-            fallback = _write_archive_system_tar(out, arcbase, walk.files, cancel=cancel)
+            fallback = _write_archive_system_tar(out, arcbase, walk.files, cancel=cancel, on_finalize=finalize)
             if fallback is not None:
-                _write_archive(out, arcbase, walk.files, cancel=cancel)
+                _write_archive(out, arcbase, walk.files, cancel=cancel, on_finalize=finalize)
                 note = f" (system-tar unavailable: {fallback}; used python engine)"
         else:
-            _write_archive(out, arcbase, walk.files, cancel=cancel)
+            _write_archive(out, arcbase, walk.files, cancel=cancel, on_bytes=on_bytes, on_finalize=finalize)
         size = out.stat().st_size
         return StepResult(
             label,
@@ -402,7 +441,12 @@
     return seen
 
 
-def _write_archive(out: Path, arcbase: Path, files: Iterable[Path], *, cancel: threading.Event | None = None) -> None:
+def _write_archive(
+    out: Path, arcbase: Path, files: Iterable[Path], *,
+    cancel: threading.Event | None = None,
+    on_bytes: Callable[[int], None] | None = None,
+    on_finalize: Callable[[], None] | None = None,
+) -> None:
     """Stream a ``w:gz`` tarball of ``files`` to ``out`` atomically, ``chmod 600``.
 
     Replicates ``pybase.filesystem.atomic_write``'s tempfile + fsync +
@@ -418,12 +462,20 @@
     try:
         with os.fdopen(fd, "wb") as raw:
             os.fchmod(fd, _ARCHIVE_MODE)
+            done = 0
             with tarfile.open(fileobj=raw, mode="w:gz") as tar:
                 for file_path in files:
                     _check_cancel(cancel)
                     arcname = file_path.relative_to(arcbase)
+                    metadata = file_path.lstat() if on_bytes is not None else None
                     tar.add(str(file_path), arcname=str(arcname), recursive=False)
+                    if metadata is not None:
+                        if stat.S_ISREG(metadata.st_mode):
+                            done += metadata.st_size
+                        on_bytes(done)
                 _check_cancel(cancel)
+            if on_finalize is not None:
+                on_finalize()
             raw.flush()
             os.fsync(raw.fileno())
         _check_cancel(cancel)
@@ -435,7 +487,8 @@
 
 
 def _write_archive_system_tar(
-    out: Path, arcbase: Path, files: Iterable[Path], *, cancel: threading.Event | None = None
+    out: Path, arcbase: Path, files: Iterable[Path], *, cancel: threading.Event | None = None,
+    on_finalize: Callable[[], None] | None = None,
 ) -> str | None:
     """Archive ``files`` via system ``tar --null -T -``, atomically, ``chmod 600``.
 
@@ -465,6 +518,8 @@
             stderr = stderr_bytes.decode("utf-8", "replace").strip().splitlines()
             detail = stderr[-1] if stderr else f"exit {returncode}"
             return f"tar exited {returncode}: {detail}"
+        if on_finalize is not None:
+            on_finalize()
         # Match the Python engine's durability: fsync the finished temp archive
         # before atomically swapping it into place.
         archive_fd = os.open(str(tmp_path), os.O_RDONLY)
```

## Mutant 1: Byte accounting obtains lstat after tar.add

```diff
--- baseline
+++ mutant-1
@@ -467,8 +467,8 @@
                 for file_path in files:
                     _check_cancel(cancel)
                     arcname = file_path.relative_to(arcbase)
+                    tar.add(str(file_path), arcname=str(arcname), recursive=False)
                     metadata = file_path.lstat() if on_bytes is not None else None
-                    tar.add(str(file_path), arcname=str(arcname), recursive=False)
                     if metadata is not None:
                         if stat.S_ISREG(metadata.st_mode):
                             done += metadata.st_size
```

Exact output:

```text
.....................................                                    [100%]
37 passed, 18 deselected in 0.45s
EXIT 0
RESTORED True
```

Weak point 1: test_input_bytes_counts_regular_paths_and_hardlinks_but_not_directories_or_symlinks - accounting after add reads changed source metadata - mutate file size inside patched tar.add; assert pre-add size is counted.

## Mutant 2: Scanning event emitted after the walk

```diff
--- baseline
+++ mutant-2
@@ -184,8 +184,8 @@
             except ValueError as exc:
                 yield StepResult(label, success=False, message=str(exc))
                 return
+            walk, missing = _select_items(source, base_state, selected)
             _emit_progress(progress, ProgressEvent(label, "scanning", None, None))
-            walk, missing = _select_items(source, base_state, selected)
             _check_cancel(cancel)
             if not walk.files:
                 message = "no selected items to archive"
@@ -194,8 +194,8 @@
                 yield StepResult(label, success=True, message=message, skipped=True)
                 return
         else:
+            walk = _walk_tree(source, base_state)
             _emit_progress(progress, ProgressEvent(label, "scanning", None, None))
-            walk = _walk_tree(source, base_state)
             _check_cancel(cancel)
 
         if dry_run:
```

Exact output:

```text
.....................................                                    [100%]
37 passed, 18 deselected in 1.29s
EXIT 0
RESTORED True
```

Weak point 2: test_engine_reports_ordered_phases_and_selected_input_bytes_before_publication - scanning arrives only after walking - patch _walk_tree/_select_items to assert scanning was already delivered.

## Mutant 3: Finalization callback runs before tar stream closes

```diff
--- baseline
+++ mutant-3
@@ -474,8 +474,8 @@
                             done += metadata.st_size
                         on_bytes(done)
                 _check_cancel(cancel)
-            if on_finalize is not None:
-                on_finalize()
+                if on_finalize is not None:
+                    on_finalize()
             raw.flush()
             os.fsync(raw.fileno())
         _check_cancel(cancel)
```

Exact output:

```text
.....................................                                    [100%]
37 passed, 18 deselected in 0.11s
EXIT 0
RESTORED True
```

Weak point 3: test_input_bytes_empty_writer_finalizes_without_member_callbacks - finalization precedes successful stream close - force TarFile.close failure; assert no finalization callback.

## Mutant 4: Both writers skip durability fsync

```diff
--- baseline
+++ mutant-4
@@ -477,7 +477,8 @@
             if on_finalize is not None:
                 on_finalize()
             raw.flush()
-            os.fsync(raw.fileno())
+            pass  # deliberately omit data durability
+
         _check_cancel(cancel)
         os.replace(tmp_path, out)
     except BaseException:
@@ -524,7 +525,8 @@
         # before atomically swapping it into place.
         archive_fd = os.open(str(tmp_path), os.O_RDONLY)
         try:
-            os.fsync(archive_fd)
+            pass  # deliberately omit data durability
+
         finally:
             os.close(archive_fd)
         os.chmod(tmp_path, _ARCHIVE_MODE)
```

Exact output:

```text
.....................................                                    [100%]
37 passed, 18 deselected in 0.38s
EXIT 0
RESTORED True
```

Weak point 4: test_engine_reports_ordered_phases_and_selected_input_bytes_before_publication - both engines publish without fsync - spy fsync/replace; require fsync before publication for each engine.

## Mutant 5: Every cancellation request is ignored

```diff
--- baseline
+++ mutant-5
@@ -46,8 +46,7 @@
 
 
 def _check_cancel(cancel: threading.Event | None) -> None:
-    if cancel is not None and cancel.is_set():
-        raise ArchiveCancelled
+    return  # deliberately ignore cancellation requests
 
 
 class WalkResult:
```

Exact output:

```text
.....................................                                    [100%]
37 passed, 18 deselected in 0.10s
EXIT 0
RESTORED True
```

Weak point 5: test_engine_interrupt_is_not_swallowed_and_writer_cleans_temporary_archive - ignores every cancellation event - set cancel without raising callback exception; assert ArchiveCancelled, old output, temp cleanup.

## Mutant 6: System engine never invokes system tar

```diff
--- baseline
+++ mutant-6
@@ -501,6 +501,7 @@
     Returns:
         ``None`` on success, otherwise a reason for Python fallback.
     """
+    return "system engine deliberately disabled"
     _check_cancel(cancel)
     tar_bin = shutil.which("tar")
     if tar_bin is None:
```

Exact output:

```text
.....................................                                    [100%]
37 passed, 18 deselected in 0.08s
EXIT 0
RESTORED True
```

Weak point 6: test_engine_reports_ordered_phases_and_selected_input_bytes_before_publication - configured system engine always uses Python - spy successful _run_system_tar and forbid Python fallback.

## Mutant 7: Emitter only swallows two ordinary exception classes

```diff
--- baseline
+++ mutant-7
@@ -41,7 +41,7 @@
     if progress is not None:
         try:
             progress(event)
-        except Exception:
+        except (ValueError, RuntimeError):
             pass
 
 
```

Exact output:

```text
.....................................                                    [100%]
37 passed, 18 deselected in 0.10s
EXIT 0
RESTORED True
```

Weak point 7: test_ordinary_progress_exception_is_swallowed_after_delivering_exact_event - callbacks raising other ordinary Exception subclasses abort - parametrize OSError, TypeError, and a custom Exception subclass.

## Mutant 8: System finalization swallows genuine interruption

```diff
--- baseline
+++ mutant-8
@@ -519,7 +519,8 @@
             detail = stderr[-1] if stderr else f"exit {returncode}"
             return f"tar exited {returncode}: {detail}"
         if on_finalize is not None:
-            on_finalize()
+            with contextlib.suppress(BaseException):
+                on_finalize()
         # Match the Python engine's durability: fsync the finished temp archive
         # before atomically swapping it into place.
         archive_fd = os.open(str(tmp_path), os.O_RDONLY)
```

Exact output:

```text
.....................................                                    [100%]
37 passed, 18 deselected in 0.10s
EXIT 0
RESTORED True
```

Weak point 8: test_base_exception_is_not_swallowed_by_progress_emitter - system writer swallows propagated finalization interruption - run real system engine with finalizing callback raising KeyboardInterrupt/SystemExit; assert propagation and preserved output.

