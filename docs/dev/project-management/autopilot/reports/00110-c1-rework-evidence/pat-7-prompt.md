
You are Pat, the per-task code reviewer. Review the single task's committed
diff below. This review is READ-ONLY: report findings, change nothing.

## Task

Subject: [D1] src/tools/backup/capabilities/tar_archive.py

Description:
### Findings (verbatim)
- 🟡 src/tools/backup/capabilities/tar_archive.py:80: `TarArchive.plan` resolves `engine` without `run`'s `or _ENGINE_PYTHON` fallback. `engine: ""` now plans as `fail "unknown engine ''"`, and `Runner.run` stops on any plan `fail`. So a config that base archived with python-tarfile (reproduced) now fails in run and in `--dry-run`. That breaks the PRD rule "`--dry-run` is unchanged". (found by: ALICE, BLAKE, BOB)
- 🟡 src/tools/backup/capabilities/tar_archive.py:78: `plan` lacks `run`'s "no source configured" / "no out path configured" guard. An empty `source` plans as `run` with source `.` (the cwd) and exits 0, while the real run fails (reproduced). An empty `out` resolves to `.` with `[replaces existing]`, and two empty outs get reported as a duplicate collision. The preview does not match what a run would do. (found by: ALICE, BLAKE, BOB)
- ⚪ src/tools/backup/capabilities/tar_archive.py:161: `_run_validated` re-reads `label` and `engine` from kwargs (tar_archive.py:161-162), though `run` already computed both. Pass them as parameters instead. Additional wording: `_run_validated` parses `label` and `engine` from `kwargs` again, though `run()` already parsed them. `plan()` and `run()` also repeat the same source/out/`cast(now)` setup. This duplication is how the engine `""` drift happened. (found by: ALICE, BOB)

### Acceptance criteria
- Every quoted finding no longer reproduces.
- Add regression tests for the quoted behavioral failures before implementing fixes.
- Preserve FatalError propagation, per-instance failure reporting, independent-instance execution, and duplicate-output safety.
- Run the normal work pipeline, required quality gates, and independent per-task review.


Acceptance criteria:

- Every quoted finding no longer reproduces.
- Add regression tests for the quoted behavioral failures before implementing fixes.
- Preserve FatalError propagation, per-instance failure reporting, independent-instance execution, and duplicate-output safety.
- Run the normal work pipeline, required quality gates, and independent per-task review.


## Diff under review

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index fdfadd8b..4c9f0ded 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -20,6 +20,7 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 ### Fixed
 
 - **backup**: a source or output metadata error while planning one instance now fails only that instance; the others still run, and duplicate outputs are still rejected.
+- **backup**: `tar-archive` plans treat an empty `engine` as the default Python engine and report an empty `source` or `out` as "no source configured" or "no out path configured", the same as a run, instead of using the working directory; two instances with an empty `out` no longer report a false output collision.
 - **sysup**: a `timeout` on a captured multi-command shell step now stops the whole step; before, only bash died and the command it was waiting on kept running. Such a step runs in its own process group, so Ctrl-C is forwarded to it, a terminal prompt it raises stops it until the timeout, and a command it runs as root through `sudo` is still out of reach and survives. Interactive steps and steps without a timeout are unchanged
 
 ## [0.16.0] - 2026-10-29
diff --git a/src/tools/backup/capabilities/tar_archive.py b/src/tools/backup/capabilities/tar_archive.py
index e78a5dc1..b3c3d89e 100644
--- a/src/tools/backup/capabilities/tar_archive.py
+++ b/src/tools/backup/capabilities/tar_archive.py
@@ -75,9 +75,16 @@ class TarArchive:
 
     def plan(self: TarArchive, **kwargs: object) -> PlanEntry:
         label = _require_str(kwargs, "label", default="tar-archive")
-        source = Path(os.path.normpath(Path(_require_str(kwargs, "source")).expanduser()))
-        out = Path(_expand_stamp(_require_str(kwargs, "out"), cast("datetime | None", kwargs.get("now")))).expanduser()
-        engine = _require_str(kwargs, "engine", default=_ENGINE_PYTHON)
+        source_raw = _require_str(kwargs, "source")
+        out_raw = _require_str(kwargs, "out")
+        engine = _require_str(kwargs, "engine", default=_ENGINE_PYTHON) or _ENGINE_PYTHON
+        if not source_raw or not out_raw:
+            message = "no source configured" if not source_raw else "no out path configured"
+            source_text = str(os.path.normpath(Path(source_raw).expanduser())) if source_raw else ""
+            out_text = _expand_stamp(out_raw, cast("datetime | None", kwargs.get("now"))) if out_raw else ""
+            return PlanEntry(label, source_text, out_text, "fail", message, False)
+        source = Path(os.path.normpath(Path(source_raw).expanduser()))
+        out = Path(_expand_stamp(out_raw, cast("datetime | None", kwargs.get("now")))).expanduser()
         replaces = out.exists()
         status = "run"
         reason = ""
@@ -112,8 +119,6 @@ class TarArchive:
         source_raw = _require_str(kwargs, "source")
         out_raw = _require_str(kwargs, "out")
         engine = _require_str(kwargs, "engine", default=_ENGINE_PYTHON) or _ENGINE_PYTHON
-        excludes = _as_str_tuple(kwargs.get("excludes", ()))
-        dry_run = bool(kwargs.get("dry_run", False))
 
         if not source_raw or not out_raw:
             message = "no source configured" if not source_raw else "no out path configured"
@@ -148,19 +153,18 @@ class TarArchive:
             yield containment
             return
 
-        yield from self._run_validated(source, out, excludes, dry_run, kwargs)
+        yield from self._run_validated(label, engine, source, out, kwargs)
 
     def _run_validated(
         self: TarArchive,
+        label: str,
+        engine: str,
         source: Path,
         out: Path,
-        excludes: tuple[str, ...],
-        dry_run: bool,
         kwargs: dict[str, object],
     ) -> Iterator[StepResult]:
-        label = _require_str(kwargs, "label", default="tar-archive")
-        engine = _require_str(kwargs, "engine", default=_ENGINE_PYTHON) or _ENGINE_PYTHON
-        base_state = ExcludeState(base_excludes=frozenset(excludes))
+        dry_run = bool(kwargs.get("dry_run", False))
+        base_state = ExcludeState(base_excludes=frozenset(_as_str_tuple(kwargs.get("excludes", ()))))
         missing: list[str] = []
         bundle = "items" in kwargs
         if bundle:
diff --git a/src/tools/backup/runner.py b/src/tools/backup/runner.py
index ce9a3cb3..e643fd86 100644
--- a/src/tools/backup/runner.py
+++ b/src/tools/backup/runner.py
@@ -68,8 +68,9 @@ class Runner:
                     # (resolved with the run-wide timestamp, like the capability does)
                     configured = now.strftime(str(instance.with_.get("out", "")))
                     entry = PlanEntry(name, "", configured, "fail", f"{name} failed: {exc}", False)
-                key = os.path.normpath(os.path.expanduser(entry.out))
-                outputs.setdefault(key, []).append(name)
+                if entry.out:
+                    key = os.path.normpath(os.path.expanduser(entry.out))
+                    outputs.setdefault(key, []).append(name)
             entries.append(entry)
             keys.append(key)
 
diff --git a/tests/tools/backup/test_plan_validation.py b/tests/tools/backup/test_plan_validation.py
new file mode 100644
index 00000000..cfd81326
--- /dev/null
+++ b/tests/tools/backup/test_plan_validation.py
@@ -0,0 +1,228 @@
+from __future__ import annotations
+
+import tarfile
+from typing import TYPE_CHECKING
+
+import pytest
+from buvis.pybase.result import FatalError
+
+from backup.capabilities.tar_archive import TarArchive
+from backup.config import BackupConfig
+from backup.runner import Runner
+
+if TYPE_CHECKING:
+    from pathlib import Path
+
+    from pytest_mock import MockerFixture
+
+    from backup.step_result import PlanEntry, StepResult
+
+
+def _source(root: Path, name: str) -> Path:
+    source = root / name
+    source.mkdir(parents=True)
+    (source / "tiny.txt").write_bytes(name.encode())
+    (source / "tiny.txt-copy").write_bytes(f"{name}-copy".encode())
+    return source
+
+
+def _invoke(interface: str, mode: str, values: dict[str, object]) -> list[PlanEntry | StepResult]:
+    if interface == "capability":
+        archive = TarArchive()
+        if mode == "plan":
+            return [archive.plan(label="selected", **values)]
+        return list(archive.run(label="selected", dry_run=mode == "dry-run", **values))
+    cfg = BackupConfig.model_validate({"instances": {"selected": {"use": "tar-archive", "with": values}}})
+    runner = Runner(cfg, dry_run=mode == "dry-run")
+    selected = list(cfg.instances.items())
+    return runner.plan(selected) if mode == "plan" else list(runner.run(selected))
+
+
+def _assert_archive(out: Path, name: str) -> None:
+    with tarfile.open(out, "r:gz") as archive:
+        files = {member.name for member in archive.getmembers() if member.isfile()}
+        assert files == {f"{name}/tiny.txt", f"{name}/tiny.txt-copy"}
+        for filename, payload in (("tiny.txt", name), ("tiny.txt-copy", f"{name}-copy")):
+            member = archive.extractfile(f"{name}/{filename}")
+            assert member is not None
+            assert member.read() == payload.encode()
+
+
+def _snapshot(root: Path) -> dict[str, bytes | None]:
+    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None for path in root.rglob("*")}
+
+
+@pytest.mark.parametrize("interface", ["capability", "runner"])
+@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
+@pytest.mark.parametrize("name", ["notes", "photos"])
+def test_empty_engine_matches_omitted_python_engine(tmp_path: Path, interface: str, mode: str, name: str) -> None:
+    source = _source(tmp_path / "sources", name)
+    out = tmp_path / "archives" / f"{name}.tar.gz"
+    values = {"source": str(source), "out": str(out)}
+    omitted = _invoke(interface, "plan", values)
+    results = _invoke(interface, mode, {**values, "engine": ""})
+
+    assert len(omitted) == len(results) == 1
+    assert omitted[0].status == "run"
+    result = results[0]
+    assert result.label == "selected"
+    if mode == "plan":
+        assert result == omitted[0]
+        assert result.source == str(source)
+        assert result.out == str(out)
+        assert result.replaces is False
+    else:
+        assert result.success is True
+        assert result.skipped is False
+        assert result.out_path == str(out)
+    assert out.exists() is (mode == "run")
+    assert out.parent.exists() is (mode == "run")
+    if mode == "run":
+        _assert_archive(out, name)
+    assert (source / "tiny.txt").read_bytes() == name.encode()
+    assert (source / "tiny.txt-copy").read_bytes() == f"{name}-copy".encode()
+
+
+@pytest.mark.parametrize("interface", ["capability", "runner"])
+@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
+@pytest.mark.parametrize(("key", "message"), [("source", "no source configured"), ("out", "no out path configured")])
+@pytest.mark.parametrize("existing", [False, True])
+def test_empty_paths_fail_without_using_cwd_or_changing_artifacts(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interface: str, mode: str, key: str, message: str, existing: bool
+) -> None:
+    source = _source(tmp_path / "sources", "notes")
+    cwd = _source(tmp_path, "working")
+    monkeypatch.chdir(cwd)
+    out = tmp_path / "archives" / "notes.tar.gz"
+    if existing:
+        out.parent.mkdir()
+        out.write_bytes(b"keep existing archive")
+    values = {"source": str(source), "out": str(out), key: ""}
+    before = _snapshot(tmp_path)
+
+    results = _invoke(interface, mode, values)
+
+    assert len(results) == 1
+    result = results[0]
+    assert result.label == "selected"
+    if mode == "plan":
+        assert result.status == "fail"
+        assert result.reason == message
+        if key == "out":
+            assert result.out == ""
+            assert result.replaces is False
+    else:
+        assert result.success is False
+        assert result.skipped is False
+        assert result.message == message
+    assert _snapshot(tmp_path) == before
+
+
+def _mixed_config(tmp_path: Path) -> tuple[BackupConfig, Path]:
+    shared = tmp_path / "shared.tar.gz"
+    shared.write_bytes(b"preserve duplicate archive")
+    values = {}
+    for name in ("empty", "empty-copy", "missing", "missing-copy", "same", "same-copy", "notes", "notes-copy"):
+        source = _source(tmp_path / "sources", name)
+        out = str(tmp_path / "outputs" / f"{name}.tar.gz")
+        if name in {"empty", "empty-copy"}:
+            out = ""
+        elif name in {"same", "same-copy"}:
+            out = str(shared)
+        values[name] = {"source": "" if name in {"missing", "missing-copy"} else str(source), "out": out}
+    cfg = BackupConfig.model_validate(
+        {"instances": {name: {"use": "tar-archive", "with": value} for name, value in values.items()}}
+    )
+    return cfg, shared
+
+
+@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
+def test_runner_keeps_missing_inputs_distinct_from_collisions_and_executes_independent_instances(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
+) -> None:
+    cfg, shared = _mixed_config(tmp_path)
+    cwd = _source(tmp_path, "working")
+    before_cwd = _snapshot(cwd)
+    monkeypatch.chdir(cwd)
+    runner = Runner(cfg, dry_run=mode == "dry-run")
+    selected = list(cfg.instances.items())
+
+    results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))
+
+    assert [result.label for result in results] == list(cfg.instances)
+    for result in results:
+        name = result.label
+        if name in {"notes", "notes-copy"}:
+            assert result.status == "run" if mode == "plan" else result.success is True
+            out = tmp_path / "outputs" / f"{name}.tar.gz"
+            assert out.exists() is (mode == "run")
+            if mode == "run":
+                _assert_archive(out, name)
+            continue
+        message = "no out path configured" if name in {"empty", "empty-copy"} else "no source configured"
+        if name in {"same", "same-copy"}:
+            other = "same-copy" if name == "same" else "same"
+            message = f"output '{shared}' is also the output of '{other}'"
+        assert result.status == "fail" if mode == "plan" else result.success is False
+        assert (result.reason if mode == "plan" else result.message) == message
+    expected = {shared}
+    if mode == "run":
+        expected |= {tmp_path / "outputs" / f"{name}.tar.gz" for name in ("notes", "notes-copy")}
+    assert set(tmp_path.rglob("*.tar.gz")) == expected
+    assert shared.read_bytes() == b"preserve duplicate archive"
+    assert _snapshot(cwd) == before_cwd
+    assert (tmp_path / "outputs").exists() is (mode == "run")
+
+
+@pytest.mark.parametrize("interface", ["capability", "runner"])
+@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
+@pytest.mark.parametrize("engine", ["python-tarfile-copy", "copy-python-tarfile"])
+def test_engine_lookalikes_remain_rejected_without_archive_effects(
+    tmp_path: Path, interface: str, mode: str, engine: str
+) -> None:
+    source = _source(tmp_path / "sources", "photos")
+    out = tmp_path / "archives" / "photos.tar.gz"
+    out.parent.mkdir()
+    out.write_bytes(b"preserve rejected engine archive")
+    before = _snapshot(tmp_path)
+
+    results = _invoke(interface, mode, {"source": str(source), "out": str(out), "engine": engine})
+
+    assert len(results) == 1
+    assert results[0].label == "selected"
+    assert results[0].status == "fail" if mode == "plan" else results[0].success is False
+    message = results[0].reason if mode == "plan" else results[0].message
+    assert f"unknown engine '{engine}'" in message
+    assert _snapshot(tmp_path) == before
+
+
+@pytest.mark.parametrize("interface", ["capability", "runner"])
+@pytest.mark.parametrize("message", ["archive storage unavailable", "archive permission denied"])
+def test_fatal_archive_errors_propagate_with_empty_default_engine(
+    tmp_path: Path, mocker: MockerFixture, interface: str, message: str
+) -> None:
+    source = _source(tmp_path / "sources", "notes")
+    out = tmp_path / "notes.tar.gz"
+    mocker.patch("tarfile.open", autospec=True, side_effect=FatalError(message))
+
+    with pytest.raises(FatalError, match=message):
+        _invoke(interface, "run", {"source": str(source), "out": str(out), "engine": ""})
+
+    assert not out.exists()
+    assert (source / "tiny.txt").read_bytes() == b"notes"
+    assert (source / "tiny.txt-copy").read_bytes() == b"notes-copy"
+
+
+@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
+def test_runner_empty_selection_has_no_archive_effects(tmp_path: Path, mode: str) -> None:
+    source = _source(tmp_path / "sources", "unselected")
+    cfg = BackupConfig.model_validate(
+        {"instances": {"unselected": {"use": "tar-archive", "with": {"source": str(source), "out": ""}}}}
+    )
+    before = _snapshot(tmp_path)
+    runner = Runner(cfg, dry_run=mode == "dry-run")
+
+    results = runner.plan([]) if mode == "plan" else list(runner.run([]))
+
+    assert results == []
+    assert _snapshot(tmp_path) == before
```

## Recorded verification

The task's tests were run before this review. This is what they reported:

uv run pytest tests/tools/backup/test_plan_validation.py -q --tb=line
exit 0
58 passed in 0.20s
Required commit hooks: Ruff and mypy passed.
Style gate: clean. Split hygiene: clean.


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


