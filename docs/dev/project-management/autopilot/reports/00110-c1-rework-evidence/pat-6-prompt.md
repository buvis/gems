
You are Pat, the per-task code reviewer. Review the single task's committed
diff below. This review is READ-ONLY: report findings, change nothing.

## Task

Subject: [D1] src/tools/backup/runner.py

Description:
### Findings (verbatim)
- 🟠 src/tools/backup/runner.py:36: `Runner.run` now calls `_plan`/`capability.plan` before `_run_instance` and outside its `try/except` (src/tools/backup/runner.py:36). Any OSError from the new metadata checks escapes the generator: `out.exists()`, `is_dir`, `is_symlink`, or a RuntimeError from `resolve` on a symlink loop. `_run_plan` in src/tools/backup/cli.py catches only `FatalError`, so the user sees a raw traceback and every other selected instance is skipped. I reproduced it with one instance whose `out` sits under a chmod-000 dir, plus one good instance. At base 7f4b462 that step fails ("bad failed: [Errno 13] …") and the good instance still archives. At HEAD the run dies with PermissionError and no archive is written. `--plan` crashes the same way. No test covers this. Fix: catch per instance in `_plan` and turn the error into a `fail` entry, the same way `_run_instance` handles it. (found by: ALICE, BLAKE, BOB)
- ⚪ src/tools/backup/runner.py:62: `_plan` tests `capability is None` twice (runner.py:51 and :62, the second with `continue`). Move `outputs.setdefault(...)` into the `else` branch and drop the second check. Additional wording: `_plan` computes `os.path.normpath(os.path.expanduser(entry.out))` twice per entry, and it checks `capability is None` twice. Computing the key once in the first loop removes both repeats. (found by: ALICE, BOB)

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
index b75040d4..fdfadd8b 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -19,6 +19,7 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 
 ### Fixed
 
+- **backup**: a source or output metadata error while planning one instance now fails only that instance; the others still run, and duplicate outputs are still rejected.
 - **sysup**: a `timeout` on a captured multi-command shell step now stops the whole step; before, only bash died and the command it was waiting on kept running. Such a step runs in its own process group, so Ctrl-C is forwarded to it, a terminal prompt it raises stops it until the timeout, and a command it runs as root through `sudo` is still out of reach and survives. Interactive steps and steps without a timeout are unchanged
 
 ## [0.16.0] - 2026-10-29
diff --git a/src/tools/backup/runner.py b/src/tools/backup/runner.py
index 0b7ee0a8..ce9a3cb3 100644
--- a/src/tools/backup/runner.py
+++ b/src/tools/backup/runner.py
@@ -45,9 +45,11 @@ class Runner:
 
     def _plan(self: Runner, selected: list[tuple[str, BackupInstance]], now: datetime) -> list[PlanEntry]:
         entries = []
+        keys: list[str | None] = []
         outputs: dict[str, list[str]] = {}
         for name, instance in selected:
             capability = CAPABILITIES.get(instance.use)
+            key: str | None = None
             if capability is None:  # pragma: no cover - load_config validates this
                 entry = PlanEntry(name, "", "", "fail", f"unknown capability '{instance.use}'", False)
             else:
@@ -57,17 +59,23 @@ class Runner:
                     "excludes": list(effective_excludes(self._cfg, instance)),
                     "now": now,
                 }
-                entry = capability.plan(**call_kwargs)
+                try:
+                    entry = capability.plan(**call_kwargs)
+                except FatalError:
+                    raise
+                except Exception as exc:
+                    # keep the configured output so duplicate detection still sees it
+                    # (resolved with the run-wide timestamp, like the capability does)
+                    configured = now.strftime(str(instance.with_.get("out", "")))
+                    entry = PlanEntry(name, "", configured, "fail", f"{name} failed: {exc}", False)
+                key = os.path.normpath(os.path.expanduser(entry.out))
+                outputs.setdefault(key, []).append(name)
             entries.append(entry)
-            if capability is None:
-                continue
-            out = os.path.normpath(os.path.expanduser(entry.out))
-            outputs.setdefault(out, []).append(name)
-
-        for index, entry in enumerate(entries):
-            out = os.path.normpath(os.path.expanduser(entry.out))
-            names = outputs.get(out, [])
-            if len(names) > 1:
+            keys.append(key)
+
+        for index, (entry, out) in enumerate(zip(entries, keys, strict=True)):
+            if out is not None and len(outputs[out]) > 1:
+                names = outputs[out]
                 others = ", ".join(sorted(name for name in names if name != entry.label))
                 entries[index] = entry._replace(
                     out=out,
diff --git a/tests/tools/backup/test_plan_errors.py b/tests/tools/backup/test_plan_errors.py
new file mode 100644
index 00000000..342609b2
--- /dev/null
+++ b/tests/tools/backup/test_plan_errors.py
@@ -0,0 +1,236 @@
+from __future__ import annotations
+
+import tarfile
+from datetime import datetime
+from pathlib import Path
+from typing import TYPE_CHECKING
+
+import pytest
+from buvis.pybase.result import FatalError
+
+from backup.config import BackupConfig
+from backup.runner import Runner
+
+if TYPE_CHECKING:
+    from os import stat_result
+
+    from pytest_mock import MockerFixture
+
+
+def _config(tmp_path: Path, outputs: dict[str, Path]) -> BackupConfig:
+    instances = {}
+    for name, out in outputs.items():
+        source = tmp_path / "sources" / name
+        source.mkdir(parents=True)
+        (source / "tiny.txt").write_bytes(name.encode())
+        instances[name] = {"use": "tar-archive", "with": {"source": str(source), "out": str(out)}}
+    return BackupConfig.model_validate({"instances": instances})
+
+
+def _fail_metadata(monkeypatch: pytest.MonkeyPatch, errors: dict[Path, Exception]) -> None:
+    real_stat = Path.stat
+
+    def stat(path: Path, *, follow_symlinks: bool = True) -> stat_result:
+        if path in errors:
+            raise errors[path]
+        return real_stat(path, follow_symlinks=follow_symlinks)
+
+    monkeypatch.setattr(Path, "stat", stat)
+
+
+def _assert_archive(out: Path, name: str) -> None:
+    with tarfile.open(out, "r:gz") as archive:
+        assert {member.name for member in archive.getmembers() if member.isfile()} == {f"{name}/tiny.txt"}
+        member = archive.extractfile(f"{name}/tiny.txt")
+        assert member is not None
+        assert member.read() == name.encode()
+
+
+@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
+@pytest.mark.parametrize("error_type", [OSError, PermissionError, RuntimeError])
+@pytest.mark.parametrize("metadata", ["source", "out"])
+def test_runner_isolates_metadata_failures_and_preserves_independent_instances(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, error_type: type[Exception], metadata: str
+) -> None:
+    names = ("before", "blocked", "blocked-copy", "second-blocked", "after")
+    outputs = {name: tmp_path / "archives" / name / "daily.tar.gz" for name in names}
+    cfg = _config(tmp_path, outputs)
+    failed = ("blocked", "second-blocked")
+    messages = {name: f"{name}: {metadata} metadata unavailable" for name in failed}
+    targets = {name: tmp_path / "sources" / name if metadata == "source" else outputs[name] for name in failed}
+    runner = Runner(cfg, dry_run=mode == "dry-run")
+    with monkeypatch.context() as patch:
+        _fail_metadata(patch, {targets[name]: error_type(messages[name]) for name in failed})
+        selected = list(cfg.instances.items())
+        results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))
+    assert [result.label for result in results] == list(names)
+    for result in results:
+        out = outputs[result.label]
+        if result.label in failed:
+            if mode == "plan":
+                assert result.status == "fail"
+                assert messages[result.label] in result.reason
+            else:
+                assert result.success is False
+                assert result.skipped is False
+                assert messages[result.label] in result.message
+            assert not out.exists()
+            assert not out.parent.exists()
+        else:
+            if mode == "plan":
+                assert result.status == "run"
+                assert result.source == str(tmp_path / "sources" / result.label)
+                assert result.out == str(out)
+            else:
+                assert result.success is True
+                assert result.skipped is False
+                assert result.out_path == str(out)
+            assert out.exists() is (mode == "run")
+            assert out.parent.exists() is (mode == "run")
+            if mode == "run":
+                _assert_archive(out, result.label)
+
+
+@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
+@pytest.mark.parametrize("error_type", [OSError, PermissionError, RuntimeError])
+@pytest.mark.parametrize("metadata", ["source", "out"])
+def test_runner_rejects_every_duplicate_output_even_when_member_metadata_fails(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, error_type: type[Exception], metadata: str
+) -> None:
+    shared = tmp_path / "shared.tar.gz"
+    shared.write_bytes(b"keep existing archive")
+    colliding = ("blocked", "peer", "another-peer")
+    outputs = dict.fromkeys(colliding, shared)
+    outputs["blocked-copy"] = tmp_path / "independent" / "shared.tar.gz"
+    outputs["suffix-copy"] = tmp_path / "shared.tar.gz.copy"
+    cfg = _config(tmp_path, outputs)
+    target = tmp_path / "sources" / "blocked" if metadata == "source" else shared
+    runner = Runner(cfg, dry_run=mode == "dry-run")
+    with monkeypatch.context() as patch:
+        _fail_metadata(patch, {target: error_type(f"blocked {metadata} metadata")})
+        selected = list(cfg.instances.items())
+        results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))
+    assert [result.label for result in results] == list(outputs)
+    for result in results:
+        if result.label in colliding:
+            others = ", ".join(sorted(name for name in colliding if name != result.label))
+            message = f"output '{shared}' is also the output of '{others}'"
+            if mode == "plan":
+                assert result.status == "fail"
+                assert result.reason == message
+            else:
+                assert result.success is False
+                assert result.skipped is False
+                assert result.message == message
+        else:
+            if mode == "plan":
+                assert result.status == "run"
+                assert result.out == str(outputs[result.label])
+            else:
+                assert result.success is True
+                assert result.out_path == str(outputs[result.label])
+            assert outputs[result.label].exists() is (mode == "run")
+            if mode == "run":
+                _assert_archive(outputs[result.label], result.label)
+    assert shared.read_bytes() == b"keep existing archive"
+    assert (tmp_path / "independent").exists() is (mode == "run")
+
+
+@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
+@pytest.mark.parametrize("message", ["backup storage unavailable", "backup permission fatal"])
+@pytest.mark.parametrize("metadata", ["source", "out"])
+def test_runner_propagates_the_original_fatal_metadata_error(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, message: str, metadata: str
+) -> None:
+    out = tmp_path / "notes.tar.gz"
+    cfg = _config(tmp_path, {"notes": out})
+    fatal = FatalError(message)
+    target = tmp_path / "sources" / "notes" if metadata == "source" else out
+    runner = Runner(cfg, dry_run=mode == "dry-run")
+    with monkeypatch.context() as patch:
+        _fail_metadata(patch, {target: fatal})
+        with pytest.raises(FatalError) as raised:
+            selected = list(cfg.instances.items())
+            if mode == "plan":
+                runner.plan(selected)
+            else:
+                list(runner.run(selected))
+    assert raised.value is fatal
+    assert str(raised.value) == message
+    assert not out.exists()
+
+
+@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
+def test_runner_keeps_empty_selection_empty_without_planning_unselected_instances(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
+) -> None:
+    outputs = {name: tmp_path / "archives" / f"{name}.tar.gz" for name in ("notes", "notes-copy")}
+    cfg = _config(tmp_path, outputs)
+    errors = {tmp_path / "sources" / name: FatalError(f"unselected {name}") for name in outputs}
+    errors.update({out: FatalError(f"unselected output {name}") for name, out in outputs.items()})
+    runner = Runner(cfg, dry_run=mode == "dry-run")
+    with monkeypatch.context() as patch:
+        _fail_metadata(patch, errors)
+        results = runner.plan([]) if mode == "plan" else list(runner.run([]))
+    assert results == []
+    assert not (tmp_path / "archives").exists()
+    for name, out in outputs.items():
+        assert not out.exists()
+        assert (tmp_path / "sources" / name / "tiny.txt").read_bytes() == name.encode()
+
+
+@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
+@pytest.mark.parametrize("error_type", [OSError, PermissionError, RuntimeError])
+@pytest.mark.parametrize("now", [datetime(2026, 12, 31, 23, 59, 59), datetime(2027, 1, 1, 0, 0, 1)])
+def test_runner_rejects_timestamp_output_collisions_when_source_metadata_fails(
+    tmp_path: Path,
+    monkeypatch: pytest.MonkeyPatch,
+    mocker: MockerFixture,
+    mode: str,
+    error_type: type[Exception],
+    now: datetime,
+) -> None:
+    pattern = "archive-%Y%m%d-%H%M%S.tar.gz"
+    shared = tmp_path / "colliding" / now.strftime(pattern)
+    independent = tmp_path / "independent" / "archive.tar.gz"
+    cfg = _config(
+        tmp_path,
+        {
+            "stamped": tmp_path / "colliding" / pattern,
+            "literal": shared,
+            "independent": independent,
+        },
+    )
+    clock = mocker.patch("backup.runner.datetime", autospec=True)
+    clock.now.return_value = now
+    fallback = mocker.patch("backup.capabilities.tar_archive.datetime", autospec=True)
+    fallback.now.return_value = datetime(2001, 6, 7, 8, 9, 10)
+    runner = Runner(cfg, dry_run=mode == "dry-run")
+    with monkeypatch.context() as patch:
+        _fail_metadata(patch, {tmp_path / "sources" / "stamped": error_type("stamped source metadata")})
+        selected = list(cfg.instances.items())
+        results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))
+    assert [result.label for result in results] == ["stamped", "literal", "independent"]
+    for result in results[:2]:
+        other = "literal" if result.label == "stamped" else "stamped"
+        message = f"output '{shared}' is also the output of '{other}'"
+        if mode == "plan":
+            assert result.status == "fail"
+            assert result.reason == message
+            assert result.out == str(shared)
+        else:
+            assert result.success is False
+            assert result.skipped is False
+            assert result.message == message
+    if mode == "plan":
+        assert results[2].status == "run"
+        assert results[2].out == str(independent)
+    else:
+        assert results[2].success is True
+        assert results[2].skipped is False
+        assert results[2].out_path == str(independent)
+    assert not shared.parent.exists()
+    assert independent.exists() is (mode == "run")
+    assert independent.parent.exists() is (mode == "run")
+    if mode == "run":
+        _assert_archive(independent, "independent")
```

## Recorded verification

The task's tests were run before this review. This is what they reported:

uv run pytest tests/tools/backup/test_plan_errors.py -q --tb=line
exit 0
69 passed in 0.25s
Required commit hooks: Ruff and mypy passed.
Style gate: timestamp test function52lines; one prescribed style repair returned no edits, violation retained per cap.


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


