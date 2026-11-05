
You are Pat, the per-task code reviewer. Review the single task's committed
diff below. This review is READ-ONLY: report findings, change nothing.

## Task

Subject: [D1] src/tools/backup/capabilities/tar_archive.py

Description:
### Findings (verbatim)
- 🟡 src/tools/backup/capabilities/tar_archive.py:285: Items are normalized twice in both run and plan. Normalize once and pass the selected paths to containment and selection. (found by: ALICE, BOB)
- 🟠 src/tools/backup/capabilities/tar_archive.py:299: The new item comparison can allow output inside a selected directory on case-insensitive filesystems: items ["Config"] and out "<source>/config/archive.tar.gz" compare unequal lexically but address the same directory. Previously the whole-source guard rejected this configuration. Compare filesystem identity for existing ancestors while preserving final-symlink semantics; add coverage for both engines and every mode. (found by: BOB)


Acceptance criteria:
Every quoted finding no longer reproduces; preserve final symlink semantics, invalid-item precedence and output bytes on rejection.

## Diff under review

```diff
diff --git a/src/tools/backup/capabilities/tar_archive.py b/src/tools/backup/capabilities/tar_archive.py
index bcca78de..075d4544 100644
--- a/src/tools/backup/capabilities/tar_archive.py
+++ b/src/tools/backup/capabilities/tar_archive.py
@@ -156,20 +156,27 @@ class TarArchive:
             yield StepResult(label, success=missing_source, message=f"{reason}: {source}", skipped=missing_source)
             return
 
-        containment = _reject_out_inside_source(label, source, out, kwargs.get("items"))
+        try:
+            selected = _normalize_items(source, kwargs["items"]) if kwargs.get("items") is not None else None
+        except (ValueError, OSError) as exc:
+            yield StepResult(label, success=False, message=str(exc))
+            return
+        containment = _reject_out_inside_source(label, source, out, selected)
         if containment is not None:
             yield containment
             return
 
-        yield from self._run_validated(label, engine, source, out, kwargs)
+        yield from self._run_validated(label, engine, source, out, kwargs, selected=selected)
 
-    def _run_validated(
+    def _run_validated(  # noqa: PLR0913 — retain archive context plus normalized selection
         self: TarArchive,
         label: str,
         engine: str,
         source: Path,
         out: Path,
         kwargs: dict[str, object],
+        *,
+        selected: list[Path] | None,
     ) -> Iterator[StepResult]:
         cancel = cast("threading.Event | None", kwargs.get("cancel"))
         _check_cancel(cancel)
@@ -178,13 +185,8 @@ class TarArchive:
         progress = None if dry_run else progress
         base_state = ExcludeState(base_excludes=frozenset(_as_str_tuple(kwargs.get("excludes", ()))))
         missing: list[str] = []
-        bundle = kwargs.get("items") is not None
-        if bundle:
-            try:
-                selected = _normalize_items(source, kwargs["items"])
-            except ValueError as exc:
-                yield StepResult(label, success=False, message=str(exc))
-                return
+        bundle = selected is not None
+        if selected is not None:
             _emit_progress(progress, ProgressEvent(label, "scanning", None, None))
             try:
                 walk, missing = _select_items(source, base_state, selected)
@@ -266,7 +268,19 @@ class TarArchive:
         )
 
 
-def _reject_out_inside_source(label: str, source: Path, out: Path, items: object = None) -> StepResult | None:
+def _same_path(left: Path, right: Path) -> bool:
+    """Compare existing filesystem entries without following their final symlinks."""
+    if left == right:
+        return True
+    try:
+        return os.path.samestat(left.lstat(), right.lstat())
+    except (FileNotFoundError, NotADirectoryError):
+        return False
+
+
+def _reject_out_inside_source(
+    label: str, source: Path, out: Path, selected: list[Path] | None = None
+) -> StepResult | None:
     """Reject an ``out`` path that would be re-archived by the run.
 
     An ``out`` under ``source`` makes each run re-archive the previous run's
@@ -279,23 +293,21 @@ def _reject_out_inside_source(label: str, source: Path, out: Path, items: object
     :class:`StepResult` (the caller yields it and returns before walking),
     otherwise ``None``.
     """
-    selected: list[Path] = []
-    if items is not None:
-        try:
-            selected = _normalize_items(source, items)
-        except ValueError as exc:
-            return StepResult(label, success=False, message=str(exc))
     source_resolved = source.resolve()
     out_resolved = out.parent.resolve() / out.name
-    if out_resolved == source_resolved or (items is None and source_resolved in out_resolved.parents):
+    if _same_path(out_resolved, source_resolved) or (
+        selected is None and any(_same_path(parent, source_resolved) for parent in out_resolved.parents)
+    ):
         return StepResult(
             label,
             success=False,
             message=(f"out path {out} is inside source {source}; choose an out path outside the backup source"),
         )
-    for relative in selected:
+    for relative in selected or ():
         item = source_resolved / relative
-        if out_resolved == item or item in out_resolved.parents:
+        if _same_path(out_resolved, item) or (
+            not item.is_symlink() and any(_same_path(parent, item) for parent in out_resolved.parents)
+        ):
             return StepResult(
                 label,
                 success=False,
@@ -312,12 +324,11 @@ def _no_items_message(source: Path, missing: list[str]) -> str:
     return f"no selected items to archive in {source}{tail}"
 
 
-def _plan_items(source: Path, items: object) -> tuple[str, str]:
+def _plan_items(source: Path, selected: list[Path]) -> tuple[str, str]:
     """Return the plan ``(status, reason)`` for a bundle's ``items``."""
     try:
-        selected = _normalize_items(source, items)
         found = any(_item_present(source / item) for item in selected)
-    except (ValueError, OSError) as exc:
+    except OSError as exc:
         return "fail", str(exc)
     if found:
         return "run", ""
@@ -347,12 +358,14 @@ def _plan_source(label: str, source: Path, out: Path, items: object) -> tuple[st
         return "skip", f"source not found: {source}"
     if kind == "file":
         return "fail", f"source is not a directory: {source}"
-    containment = _reject_out_inside_source(label, source, out, items)
+    try:
+        selected = _normalize_items(source, items) if items is not None else None
+    except (ValueError, OSError) as exc:
+        return "fail", str(exc)
+    containment = _reject_out_inside_source(label, source, out, selected)
     if containment is not None:
         return "fail", containment.message
-    if items is not None:
-        return _plan_items(source, items)
-    return "run", ""
+    return _plan_items(source, selected) if selected is not None else ("run", "")
 
 
 def _item_present(path: Path) -> bool:
diff --git a/tests/tools/backup/test_bundle_case_containment.py b/tests/tools/backup/test_bundle_case_containment.py
new file mode 100644
index 00000000..1ed96998
--- /dev/null
+++ b/tests/tools/backup/test_bundle_case_containment.py
@@ -0,0 +1,153 @@
+from __future__ import annotations
+
+import tarfile
+from pathlib import Path
+
+import pytest
+
+from backup.capabilities.tar_archive import TarArchive
+
+
+@pytest.fixture(params=["python-tarfile", "system-tar"])
+def engine(request: pytest.FixtureRequest) -> str:
+    return request.param
+
+
+@pytest.fixture(params=["run", "dry_run", "plan"])
+def mode(request: pytest.FixtureRequest) -> str:
+    return request.param
+
+
+def _outcome(source: Path, out: Path, engine: str, mode: str, items: object) -> tuple[bool, str]:
+    kwargs = {"label": "bundle", "source": str(source), "out": str(out), "engine": engine, "items": items}
+    if mode == "plan":
+        entry = TarArchive().plan(**kwargs)
+        assert entry.status in {"run", "fail"}
+        return entry.status == "run", entry.reason
+    (result,) = list(TarArchive().run(**kwargs, dry_run=mode == "dry_run"))
+    return result.success, result.message
+
+
+def _snapshot(source: Path) -> dict[str, bytes | str | None]:
+    return {
+        str(path.relative_to(source)): (
+            str(path.readlink()) if path.is_symlink() else path.read_bytes() if path.is_file() else None
+        )
+        for path in source.rglob("*")
+    }
+
+
+def _case_alias(directory: Path) -> Path:
+    alias = directory.with_name(directory.name.swapcase())
+    if not alias.exists() or not alias.samefile(directory):
+        pytest.skip("case-alias containment requires a real case-insensitive filesystem")
+    return alias
+
+
+class TestBundleCaseContainment:
+    @pytest.mark.parametrize("selected", ["Config", "Profiles"])
+    @pytest.mark.parametrize("out_rel", ["", "archive.tar.gz", "new/deep/archive.tar.gz"])
+    def test_case_alias_of_selected_directory_rejects_output_without_changes(
+        self, tmp_path: Path, engine: str, mode: str, selected: str, out_rel: str
+    ) -> None:
+        source = tmp_path / "source"
+        directory = source / selected
+        directory.mkdir(parents=True)
+        (directory / "settings").write_bytes(b"selected settings")
+        (source / "other").write_bytes(b"also selected")
+        alias = _case_alias(directory)
+        out = alias / out_rel if out_rel else alias
+        if out_rel == "archive.tar.gz":
+            out.write_bytes(b"previous archive")
+        before = _snapshot(source)
+
+        success, message = _outcome(source, out, engine, mode, ["other", selected])
+
+        assert success is False
+        assert "inside selected item" in message
+        assert str(out) in message
+        assert str(directory) in message
+        assert _snapshot(source) == before
+
+    @pytest.mark.parametrize("selected", ["Config", "Profiles"])
+    def test_near_miss_sibling_allows_output_and_keeps_every_selected_item(
+        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine: str, mode: str, selected: str
+    ) -> None:
+        source = tmp_path / "source"
+        directory = source / selected
+        directory.mkdir(parents=True)
+        (directory / "settings").write_bytes(selected.encode())
+        (source / "other").write_bytes(b"second item")
+        sibling = source / f"{selected}-backup"
+        sibling.mkdir()
+        out = sibling / "archive.tar.gz"
+        out.write_bytes(b"previous archive")
+        before = _snapshot(source)
+        monkeypatch.chdir(sibling)
+
+        success, _ = _outcome(source, Path(out.name), engine, mode, [selected, "other"])
+
+        assert success is True
+        if mode == "run":
+            with tarfile.open(out, "r:gz") as archive:
+                assert set(archive.getnames()) == {selected, f"{selected}/settings", "other"}
+                assert archive.extractfile(f"{selected}/settings").read() == selected.encode()
+                assert archive.extractfile("other").read() == b"second item"
+        else:
+            assert _snapshot(source) == before
+
+    @pytest.mark.parametrize("out_parent", ["target", "link"])
+    def test_final_symlink_items_allow_output_in_target_without_archiving_target_contents(
+        self, tmp_path: Path, engine: str, mode: str, out_parent: str
+    ) -> None:
+        source = tmp_path / "source"
+        target = source / "target"
+        target.mkdir(parents=True)
+        (target / "private").write_bytes(b"do not archive")
+        (source / "link").symlink_to("target", target_is_directory=True)
+        (source / "broken").symlink_to("absent")
+        (source / "other").write_bytes(b"keep")
+        out = source / out_parent / "archive.tar.gz"
+        out.write_bytes(b"previous archive")
+        before = _snapshot(source)
+
+        success, _ = _outcome(source, out, engine, mode, ["link", "broken", "other"])
+
+        assert success is True
+        assert (target / "private").read_bytes() == b"do not archive"
+        assert (source / "link").readlink() == Path("target")
+        if mode == "run":
+            with tarfile.open(out, "r:gz") as archive:
+                members = {member.name: member for member in archive.getmembers()}
+                assert set(members) == {"link", "broken", "other"}
+                assert members["link"].issym()
+                assert members["link"].linkname == "target"
+                assert members["broken"].issym()
+                assert members["broken"].linkname == "absent"
+                assert archive.extractfile("other").read() == b"keep"
+        else:
+            assert _snapshot(source) == before
+
+    @pytest.mark.parametrize(
+        ("items", "message"),
+        [
+            ([], "items must not be empty"),
+            (["Config", "../escape"], "invalid item '../escape': must be a relative path inside the source"),
+            (["Config", None], "items must be a list of relative paths"),
+        ],
+    )
+    def test_invalid_items_take_precedence_over_output_containment(
+        self, tmp_path: Path, engine: str, mode: str, items: object, message: str
+    ) -> None:
+        source = tmp_path / "source"
+        directory = source / "Config"
+        directory.mkdir(parents=True)
+        out = directory / "archive.tar.gz"
+        out.write_bytes(b"previous archive")
+        before = _snapshot(source)
+
+        success, reason = _outcome(source, out, engine, mode, items)
+
+        assert success is False
+        assert reason == message
+        assert _snapshot(source) == before
```

## Recorded verification

The task's tests were run before this review. This is what they reported:

uv run pytest tests/tools/backup/test_bundle_case_containment.py -q --tb=line
Exit: 0
........................................................................ [ 92%]
......                                                                   [100%]
78 passed in 0.17s


Judge only from this prompt: the diff above, the task text, and this recorded
result. Do not read other files, run commands, or re-run the tests. What is not
in this prompt is not evidence, and a finding you cannot ground in what is here
is one you should not report.

# Simplification Mandate (step 5.7 reviewer-prompt appendix)

Append this block **verbatim** to every per-task code-reviewer prompt (see
`SKILL.md` step 5.7). It ships inside the prompt, so it must stay
self-contained.

> Beyond bugs, actively hunt for simplification in the diff under review. For
> every added or changed file, ask "what would make this simpler to read
> without changing what it does?" and flag concrete behavior-preserving
> opportunities to: reduce complexity (needless indirection, dead branches,
> single-caller abstractions, nesting deeper than 4 levels, functions over 50
> lines); eliminate redundancy (logic duplicated within the diff or against
> existing code, a helper that reimplements a stdlib or existing utility);
> improve naming (names that state intent, no opaque abbreviations); and
> remove dead code. Follow CLAUDE.md / AGENTS.md conventions and the
> surrounding code's style.
>
> Report each concrete behavior-preserving simplification as a LOW finding,
> with file:line, the current shape, and the simpler replacement. LOW findings
> are carried to the PRD-level review, never retried here.
>
> Do not over-simplify: never propose a change that trades clarity for
> brevity, drops error handling, collapses a deliberate boundary, or removes a
> documented invariant. Simpler means easier to read and maintain, not shorter
> at any cost. If a change would alter behavior, it is out of scope — do not
> flag it.


## Reporting contract

Report one finding per line, in exactly this shape:

SEVERITY | file:line | issue | fix

Severities are CRITICAL, HIGH, MEDIUM, LOW.

Severity has a fixed meaning here, and it decides what happens next. MEDIUM is
reserved for a correctness or security defect this diff introduces that its own
tests do not catch: a wrong result, an unhandled error path, data loss,
injection, secret exposure, or a missing authorization check. Style, naming,
duplication, structure and maintainability are LOW, and so is every
behavior-preserving simplification, whatever its size. A LOW is noted and
carried to the PRD-level review; it is never retried in this loop.

If the diff has no findings, emit the literal line:

NO FINDINGS

## Closure verdicts (only when the description carries a findings block)

When the Description above contains a `### Findings (verbatim)` block, this is
a rework task and each quoted finding is a claim to check. Before your findings
lines, emit one verdict per quoted finding, in this shape:

CLOSURE | resolved|unresolved | <the finding, quoted> | <one line of evidence from the diff>

Judge each finding against the diff, not against the commit message and not
against how clean the code reads. A diff that improves the file while leaving
the quoted defect reachable is `unresolved`. Quote the line that resolves it,
or say what still reaches the defect. Emit a verdict for every quoted finding,
including ones you judge already fixed elsewhere.


