Same task, next review cycle. You already reviewed this task's diff earlier in
this conversation; below is only what changed since.

You already reviewed a6dfa4a7..64458f89 earlier in this conversation. That range is unchanged and is not repeated here.

## Findings you raised, sent to the implementor

CLOSURE | resolved | "Items are normalized twice in both run and plan. Normalize once and pass the selected paths to containment and selection." | `run` and `_plan_source` each call `_normalize_items` once. They pass `selected` to `_reject_out_inside_source` and then to `_run_validated` or `_plan_items`. No second call remains. Invalid items are rejected before containment, and `test_invalid_items_take_precedence_over_output_containment` covers this.

CLOSURE | resolved | "The new item comparison can allow output inside a selected directory on case-insensitive filesystems... Compare filesystem identity for existing ancestors while preserving final-symlink semantics; add coverage for both engines and every mode." | `_same_path` uses `os.samestat` on `lstat`. It compares `out_resolved` and every ancestor in `out_resolved.parents` against `item`, so `config` and `Config` match. The new tests cover both engines and the run, dry_run and plan modes. The final-symlink test confirms output into a symlink item's target is still allowed. The tests skip on case-sensitive filesystems.

MEDIUM | src/tools/backup/capabilities/tar_archive.py:276 | `_same_path` catches only `FileNotFoundError` and `NotADirectoryError`. `lstat` can also raise `PermissionError` or `ELOOP`/`ENAMETOOLONG` `OSError`. The old containment check was lexical and did no I/O. The new calls in `_reject_out_inside_source` sit outside any try/except, in both `run` and `_plan_source`. | An `out` path under an ancestor directory without search permission makes `lstat(out_resolved)` raise `PermissionError`. `run` then raises a traceback instead of yielding a failed `StepResult`, and `plan` raises instead of returning `fail`. Catch `OSError` in `_same_path` and return `False`, or let the caller turn it into a failed result. Add a test for the unsearchable-ancestor case.

LOW | src/tools/backup/capabilities/tar_archive.py:309 | `not item.is_symlink()` is redundant. `out_resolved.parents` come from a resolved parent, so they are never symlinks, and `_same_path` on a symlink `item` already cannot match a directory. The check costs an extra `lstat` per item. | Drop the guard and keep `any(_same_path(parent, item) for parent in out_resolved.parents)`. The final-symlink test still passes.

LOW | tests/tools/backup/test_bundle_case_containment.py:37 | The case-alias tests call `pytest.skip` on case-sensitive filesystems, so the new identity logic is untested on Linux CI. | Add a hardlink or bind-style test, or a monkeypatched `lstat`, that exercises `_same_path` where case is not the alias mechanism.

Verified MEDIUM retry: ........................................................................ [ 80%]
..................                                                       [100%]
90 passed in 0.26s


## What changed since your last review

```diff
diff --git a/src/tools/backup/capabilities/tar_archive.py b/src/tools/backup/capabilities/tar_archive.py
index 075d4544..b26d5c1b 100644
--- a/src/tools/backup/capabilities/tar_archive.py
+++ b/src/tools/backup/capabilities/tar_archive.py
@@ -158,10 +158,10 @@ class TarArchive:
 
         try:
             selected = _normalize_items(source, kwargs["items"]) if kwargs.get("items") is not None else None
+            containment = _reject_out_inside_source(label, source, out, selected)
         except (ValueError, OSError) as exc:
             yield StepResult(label, success=False, message=str(exc))
             return
-        containment = _reject_out_inside_source(label, source, out, selected)
         if containment is not None:
             yield containment
             return
@@ -360,9 +360,9 @@ def _plan_source(label: str, source: Path, out: Path, items: object) -> tuple[st
         return "fail", f"source is not a directory: {source}"
     try:
         selected = _normalize_items(source, items) if items is not None else None
+        containment = _reject_out_inside_source(label, source, out, selected)
     except (ValueError, OSError) as exc:
         return "fail", str(exc)
-    containment = _reject_out_inside_source(label, source, out, selected)
     if containment is not None:
         return "fail", containment.message
     return _plan_items(source, selected) if selected is not None else ("run", "")
diff --git a/tests/tools/backup/test_bundle_case_containment.py b/tests/tools/backup/test_bundle_case_containment.py
index 1ed96998..2f310435 100644
--- a/tests/tools/backup/test_bundle_case_containment.py
+++ b/tests/tools/backup/test_bundle_case_containment.py
@@ -1,5 +1,6 @@
 from __future__ import annotations
 
+import os
 import tarfile
 from pathlib import Path
 
@@ -45,6 +46,35 @@ def _case_alias(directory: Path) -> Path:
 
 
 class TestBundleCaseContainment:
+    @pytest.mark.parametrize("error", ["output identity permission denied", "archive metadata access denied"])
+    def test_output_identity_permission_error_fails_without_replacing_output(
+        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine: str, mode: str, error: str
+    ) -> None:
+        source = tmp_path.resolve() / "source"
+        directory = source / "Config"
+        directory.mkdir(parents=True)
+        (directory / "settings").write_bytes(b"selected settings")
+        (source / "other").write_bytes(b"also selected")
+        sibling = source / "Config-backup"
+        sibling.mkdir()
+        out = sibling / "archive.tar.gz"
+        out.write_bytes(error.encode())
+        before = _snapshot(source)
+        real_lstat = Path.lstat
+
+        def denied_lstat(path: Path) -> os.stat_result:
+            if path == out:
+                raise PermissionError(error)
+            return real_lstat(path)
+
+        with monkeypatch.context() as patch:
+            patch.setattr(Path, "lstat", denied_lstat)
+            success, message = _outcome(source, out, engine, mode, ["Config", "other"])
+
+        assert success is False
+        assert error in message
+        assert _snapshot(source) == before
+
     @pytest.mark.parametrize("selected", ["Config", "Profiles"])
     @pytest.mark.parametrize("out_rel", ["", "archive.tar.gz", "new/deep/archive.tar.gz"])
     def test_case_alias_of_selected_directory_rejects_output_without_changes(
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
