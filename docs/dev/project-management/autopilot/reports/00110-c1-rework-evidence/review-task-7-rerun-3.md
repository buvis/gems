Same task, next review cycle. You already reviewed this task's diff earlier in
this conversation; below is only what changed since.

You already reviewed ee0bc71fc84c2309070ec58a0913cb8364229509..9b266a1d earlier. That range is unchanged. This delta is only the confirmed shared-input closure repair.

## Findings you raised, sent to the implementor

CLOSURE | unresolved | `plan` and `run` (~119-125) both carry the same source/out parse, `or _ENGINE_PYTHON` fallback and "no source / no out path configured" selection | The delta only changes `(\"\", \"fail\")` to `(\"\", \"run\")` in `tests/tools/backup/test_plan.py:388`. No production line moves, so both copies still exist.
LOW | src/tools/backup/capabilities/tar_archive.py:78-87 | `plan` and `run` (~119-125) still duplicate the source/out parse, the `or _ENGINE_PYTHON` fallback and the missing-input message selection. | Extract one shared helper such as `_parse_inputs(kwargs)` and call it from both. This is carried to the PRD-level review as prescribed.

The confirmed unresolved original finding is now repaired through shared _parse_inputs, _missing_input, and _resolve_paths helpers called by both plan and run. Label and engine remain passed into _run_validated. Coordinator verified exact task regressions plus corrected legacy engine cases: 64 passed in0.45s, exit0. Commit hooks Ruff/mypy passed. Split hygiene clean. Style checker flags the pre-existing63line _write_archive_system_tar after adjacent helper insertion; its complete AST is identical to task7base, so no unrelated archive writer refactor was made. This is final permitted Pat cycle3.


## What changed since your last review

```diff
diff --git a/src/tools/backup/capabilities/tar_archive.py b/src/tools/backup/capabilities/tar_archive.py
index b3c3d89e..d9b174f3 100644
--- a/src/tools/backup/capabilities/tar_archive.py
+++ b/src/tools/backup/capabilities/tar_archive.py
@@ -74,17 +74,13 @@ class TarArchive:
         return {"source": "", "out": "", "engine": _ENGINE_PYTHON, "items": None}
 
     def plan(self: TarArchive, **kwargs: object) -> PlanEntry:
-        label = _require_str(kwargs, "label", default="tar-archive")
-        source_raw = _require_str(kwargs, "source")
-        out_raw = _require_str(kwargs, "out")
-        engine = _require_str(kwargs, "engine", default=_ENGINE_PYTHON) or _ENGINE_PYTHON
-        if not source_raw or not out_raw:
-            message = "no source configured" if not source_raw else "no out path configured"
+        label, engine, source_raw, out_raw, now = _parse_inputs(kwargs)
+        message = _missing_input(source_raw, out_raw)
+        if message:
             source_text = str(os.path.normpath(Path(source_raw).expanduser())) if source_raw else ""
-            out_text = _expand_stamp(out_raw, cast("datetime | None", kwargs.get("now"))) if out_raw else ""
+            out_text = _expand_stamp(out_raw, now) if out_raw else ""
             return PlanEntry(label, source_text, out_text, "fail", message, False)
-        source = Path(os.path.normpath(Path(source_raw).expanduser()))
-        out = Path(_expand_stamp(out_raw, cast("datetime | None", kwargs.get("now")))).expanduser()
+        source, out = _resolve_paths(source_raw, out_raw, now)
         replaces = out.exists()
         status = "run"
         reason = ""
@@ -115,24 +111,13 @@ class TarArchive:
         return PlanEntry(label, str(source), str(out), status, reason, replaces)
 
     def run(self: TarArchive, **kwargs: object) -> Iterator[StepResult]:
-        label = _require_str(kwargs, "label", default="tar-archive")
-        source_raw = _require_str(kwargs, "source")
-        out_raw = _require_str(kwargs, "out")
-        engine = _require_str(kwargs, "engine", default=_ENGINE_PYTHON) or _ENGINE_PYTHON
-
-        if not source_raw or not out_raw:
-            message = "no source configured" if not source_raw else "no out path configured"
+        label, engine, source_raw, out_raw, now = _parse_inputs(kwargs)
+        message = _missing_input(source_raw, out_raw)
+        if message:
             yield StepResult(label, success=False, message=message)
             return
 
-        # Normalize `.`/`..` LEXICALLY (os.path.normpath, not resolve()) before
-        # walking: a source like `parent/child/..` would otherwise be walked as
-        # given and produce member names like `..` / `../child` (an unsafe
-        # archive that also breaks the documented source-name prefix). normpath
-        # collapses the segments without following symlinks, so the
-        # symlink-confinement guarantee is untouched.
-        source = Path(os.path.normpath(Path(source_raw).expanduser()))
-        out = Path(_expand_stamp(out_raw, cast("datetime | None", kwargs.get("now")))).expanduser()
+        source, out = _resolve_paths(source_raw, out_raw, now)
 
         if engine not in (_ENGINE_PYTHON, _ENGINE_SYSTEM_TAR):
             yield StepResult(
@@ -492,6 +477,35 @@ def _write_archive_system_tar(out: Path, arcbase: Path, files: Iterable[Path]) -
     return None
 
 
+def _parse_inputs(kwargs: Mapping[str, object]) -> tuple[str, str, str, str, datetime | None]:
+    """Parse label, engine, raw source/out and ``now``; an empty engine means the python engine."""
+    return (
+        _require_str(kwargs, "label", default="tar-archive"),
+        _require_str(kwargs, "engine", default=_ENGINE_PYTHON) or _ENGINE_PYTHON,
+        _require_str(kwargs, "source"),
+        _require_str(kwargs, "out"),
+        cast("datetime | None", kwargs.get("now")),
+    )
+
+
+def _missing_input(source_raw: str, out_raw: str) -> str:
+    """Return the missing-input message, or ``""`` when both source and out are set."""
+    if not source_raw:
+        return "no source configured"
+    return "" if out_raw else "no out path configured"
+
+
+def _resolve_paths(source_raw: str, out_raw: str, now: datetime | None) -> tuple[Path, Path]:
+    # Normalize `.`/`..` LEXICALLY (os.path.normpath, not resolve()) before
+    # walking: a source like `parent/child/..` would otherwise be walked as
+    # given and produce member names like `..` / `../child` (an unsafe
+    # archive that also breaks the documented source-name prefix). normpath
+    # collapses the segments without following symlinks, so the
+    # symlink-confinement guarantee is untouched.
+    source = Path(os.path.normpath(Path(source_raw).expanduser()))
+    return source, Path(_expand_stamp(out_raw, now)).expanduser()
+
+
 def _require_str(kwargs: Mapping[str, object], key: str, *, default: str = "") -> str:
     value = kwargs.get(key, default)
     return value if isinstance(value, str) else default
```

Judge two things, in this order:

1. For each finding above, is it resolved by this delta? Ground the verdict in a
   line of the delta, not in how clean the code now reads. A change that
   improves the file while leaving the defect reachable is not resolved.
   **Re-emit every finding you judge unresolved as a contract line of its own**,
   carrying the severity and `file:line` it had before. That line is the only
   thing that carries an unresolved finding out of this cycle: silence reads as
   fixed, and the defect ships.
2. Report new findings from THIS delta only. Do not re-report anything else from
   the earlier range — you already reviewed it — and do not re-raise a finding
   you are calling resolved.

Judge from this prompt and what you already read in this conversation.

Your reporting contract is unchanged: the one you were given at the top of this
conversation (`agents/pat.md`). Same line shape, same severities, and CLOSURE
verdicts still apply wherever they applied on the first dispatch. Emit
`NO FINDINGS` only when the delta is clean AND every finding above is resolved.
