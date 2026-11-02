from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterator
from io import StringIO
from pathlib import Path

import pytest
from buvis.pybase.adapters import console
from rich.console import Console
from rich.text import Text

import backup.cli as backup_cli
from backup.capabilities import CAPABILITIES
from backup.config import BackupConfig, BackupInstance
from backup.runner import Runner
from backup.step_result import PlanEntry, ProgressEvent, StepResult


class StatusRecorder:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.events: list[tuple[str, object]] = []
        self.current = ""
        self.running = False
        self.interrupt = False

    def status(self, message: str) -> StatusRecorder:
        self.created.append(message)
        return self

    def start(self) -> None:
        self.running = True
        self.events.append(("start", self.current))

    def stop(self) -> None:
        self.running = False
        self.events.append(("stop", self.current))

    def update(self, message: Text, **kwargs: object) -> None:
        assert isinstance(message, Text)
        self.current = message.plain
        self.events.append(("update", self.current))
        if self.interrupt:
            self.interrupt = False
            raise KeyboardInterrupt


@pytest.fixture
def cli_display(monkeypatch: pytest.MonkeyPatch) -> tuple[StatusRecorder, StringIO]:
    stream = StringIO()
    monkeypatch.setattr(console, "console", Console(file=stream, width=240, color_system=None))
    recorder = StatusRecorder()
    monkeypatch.setattr(console, "status", recorder.status)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    return recorder, stream


class ControlledCapability:
    inputs: dict[str, object] = {}

    def __init__(self, results: dict[str, StepResult], *, progress: bool = True) -> None:
        self.results = results
        self.progress = progress
        self.closed: list[str] = []

    def plan(self, **kwargs: object) -> PlanEntry:
        label = str(kwargs["label"])
        return PlanEntry(label, f"/source/{label}", f"/out/{label}.tar.gz", "run", "", False)

    def run(self, **kwargs: object) -> Iterator[StepResult]:
        label = str(kwargs["label"])
        try:
            callback = kwargs.get("progress")
            if self.progress and callable(callback):
                callback(ProgressEvent(label, "archiving", 7, 19))
                callback(ProgressEvent(label, "finalizing", 19, 19))
            yield self.results[label]
        finally:
            self.closed.append(label)


def controlled_plan(
    monkeypatch: pytest.MonkeyPatch,
    results: list[StepResult],
    *,
    progress: bool = True,
) -> tuple[BackupConfig, list[tuple[str, BackupInstance]], ControlledCapability]:
    capability = ControlledCapability({result.label: result for result in results}, progress=progress)
    monkeypatch.setitem(CAPABILITIES, "cli-progress-fixture", capability)
    instances = {result.label: BackupInstance(use="cli-progress-fixture") for result in results}
    return BackupConfig(instances=instances), list(instances.items()), capability


def result_lines() -> list[StepResult]:
    return [
        StepResult("docs", True, "first archive ready"),
        StepResult("docs-old", False, "second archive denied"),
        StepResult("optional", True, "optional source absent", skipped=True),
    ]


class TestCliProgressFormat:
    @pytest.mark.parametrize(
        "event,elapsed,expected",
        [
            (ProgressEvent("docs", "archiving", 37, 100), 65.9, "docs archiving [37%] 1:05"),
            (ProgressEvent("docs-old", "archiving", 7, 19), 9.9, "docs-old archiving [36%] 0:09"),
            (ProgressEvent("docs", "archiving", 100, 100), 3605, "docs archiving [99%] 60:05"),
            (ProgressEvent("docs-old", "archiving", 200, 100), -3, "docs-old archiving [99%] 0:00"),
            (ProgressEvent("git", "scanning", None, None), 2, "git scanning 0:02"),
            (ProgressEvent("git-old", "archiving", None, 700), 120, "git-old archiving 2:00"),
            (ProgressEvent("git", "archiving", 7, None), 61, "git archiving 1:01"),
            (ProgressEvent("git-old", "archiving", 0, 0), 59, "git-old archiving 0:59"),
            (ProgressEvent("git", "archiving", 0, -1), 0, "git archiving 0:00"),
            (ProgressEvent("git", "finalizing", 7, 19), 120, "git finalizing 2:00"),
            (ProgressEvent("git-old", "finalizing", 100, 100), 3661, "git-old finalizing 61:01"),
            (ProgressEvent("", "scanning", None, None), -0.5, " scanning 0:00"),
        ],
    )
    def test_format_uses_input_byte_floor_caps_and_unbounded_minutes(
        self,
        event: ProgressEvent,
        elapsed: float,
        expected: str,
    ) -> None:
        assert backup_cli._format_progress(event, elapsed) == expected

    @pytest.mark.parametrize(
        "done,total,percent",
        [(25, 100, 25), (1, 3, 33), (2, 7, 28), (13, 29, 44), (47, 64, 73), (1001, 4096, 24)],
    )
    def test_format_percentage_handles_varied_byte_ratios(self, done: int, total: int, percent: int) -> None:
        event = ProgressEvent("arbitrary", "archiving", done, total)
        assert backup_cli._format_progress(event, 65) == f"arbitrary archiving [{percent}%] 1:05"


class TestCliLiveProgress:
    def test_cli_three_active_labels_preserve_order_and_elapsed_across_phase_changes(
        self,
        cli_display: tuple[StatusRecorder, StringIO],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        recorder, _ = cli_display
        clock = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: clock[0])
        live = backup_cli._LiveProgress()
        try:
            live.on_progress(ProgressEvent("docs", "scanning", None, None))
            clock[0] = 130.0
            live.on_progress(ProgressEvent("docs-old", "scanning", None, None))
            clock[0] = 160.0
            live.on_progress(ProgressEvent("photos", "scanning", None, None))
            clock[0] = 165.0
            live.on_progress(ProgressEvent("docs", "archiving", 25, 100))
            assert recorder.current == ("docs archiving [25%] 1:05 | docs-old scanning 0:35 | photos scanning 0:05")
        finally:
            live.close()

    def test_cli_status_preserves_first_seen_time_order_and_exact_labels(
        self,
        cli_display: tuple[StatusRecorder, StringIO],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        recorder, _ = cli_display
        clock = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: clock[0])
        live = backup_cli._LiveProgress()
        live.refresh()
        live.finish("docs")
        assert recorder.created == []
        live.on_progress(ProgressEvent("[red]docs", "scanning", None, None))
        clock[0] = 165.0
        live.on_progress(ProgressEvent("[red]docs-old", "archiving", 7, 19))
        clock[0] = 170.0
        live.on_progress(ProgressEvent("[red]docs", "finalizing", 19, 19))
        assert recorder.current == "[red]docs finalizing 1:10 | [red]docs-old archiving [36%] 0:05"
        live.finish("docs")
        assert recorder.current.startswith("[red]docs finalizing 1:10 | ")
        live.finish("[red]docs")
        assert recorder.current == "[red]docs-old archiving [36%] 0:05"
        live.finish("[red]docs")
        assert recorder.running is True
        live.finish("[red]docs-old")
        assert recorder.running is False
        clock[0] = 180.0
        live.on_progress(ProgressEvent("[red]docs", "archiving", 3, 7))
        assert recorder.current == "[red]docs archiving [42%] 0:00"
        live.close()
        live.close()
        assert recorder.created == [""]
        assert [name for name, _ in recorder.events].count("start") == 2
        assert [name for name, _ in recorder.events].count("stop") == 2

    def test_cli_real_rich_status_restarts_after_all_labels_finish(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        stream = StringIO()
        monkeypatch.setattr(console, "console", Console(file=stream, force_terminal=True, width=160))
        statuses: list[object] = []
        factory = console.status

        def capture_status(message: str) -> object:
            status = factory(message)
            statuses.append(status)
            return status

        monkeypatch.setattr(console, "status", capture_status)
        live = backup_cli._LiveProgress()
        try:
            live.on_progress(ProgressEvent("[red]docs", "archiving", 7, 19))
            live.finish("[red]docs")
            live.on_progress(ProgressEvent("[red]docs-old", "finalizing", 19, 19))
            live.finish("[red]docs-old")
        finally:
            live.close()
        output = stream.getvalue()
        assert len(statuses) == 1
        assert "[red]docs archiving [36%]" in output
        assert "[red]docs-old finalizing" in output

    def test_cli_interrupted_status_update_propagates_and_close_stops_spinner(
        self,
        cli_display: tuple[StatusRecorder, StringIO],
    ) -> None:
        recorder, _ = cli_display
        live = backup_cli._LiveProgress()
        live.on_progress(ProgressEvent("docs", "scanning", None, None))
        recorder.interrupt = True
        try:
            with pytest.raises(KeyboardInterrupt):
                live.on_progress(ProgressEvent("docs-old", "archiving", 7, 19))
        finally:
            live.close()
        assert recorder.running is False
        assert "docs-old archiving [36%]" in recorder.current


class TestCliProgressRunPlan:
    @pytest.mark.parametrize("dry_run,verb", [(False, "archived"), (True, "previewed")])
    def test_cli_report_summary_counts_each_outcome_and_describes_dry_run(
        self,
        cli_display: tuple[StatusRecorder, StringIO],
        dry_run: bool,
        verb: str,
    ) -> None:
        _, stream = cli_display
        assert backup_cli._report_steps(result_lines(), dry_run=dry_run) is True
        assert stream.getvalue().splitlines()[-1].endswith(f"{verb} 1, skipped 1, failed 1")

    @pytest.mark.parametrize(
        "result,marker",
        [
            (StepResult("docs", True, "first archive ready"), "✔"),
            (StepResult("optional", True, "optional source absent", skipped=True), "⚠"),
            (StepResult("docs-old", False, "second archive denied"), "✘"),
        ],
    )
    def test_cli_result_output_uses_the_outcome_severity(
        self,
        cli_display: tuple[StatusRecorder, StringIO],
        result: StepResult,
        marker: str,
    ) -> None:
        _, stream = cli_display
        backup_cli._report_steps([result])
        lines = [line for line in stream.getvalue().splitlines() if result.message in line]
        assert len(lines) == 1
        assert lines[0].lstrip().startswith(marker)
        assert result.message in lines[0]

    def test_cli_skipped_success_keeps_success_exit_and_skip_count(
        self,
        cli_display: tuple[StatusRecorder, StringIO],
    ) -> None:
        _, stream = cli_display
        result = StepResult("optional", True, "optional source absent", skipped=True)
        assert backup_cli._report_steps([result]) is False
        assert stream.getvalue().splitlines()[-1].endswith("archived 0, skipped 1, failed 0")

    def test_cli_live_runner_tick_refreshes_elapsed_without_new_progress(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cli_display: tuple[StatusRecorder, StringIO],
    ) -> None:
        recorder, _ = cli_display
        cfg, plan, capability = controlled_plan(monkeypatch, [StepResult("docs", True, "ready")], progress=False)
        clock = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: clock[0])
        refreshed: list[str] = []
        original = Runner.__init__

        def initialize(runner: Runner, *args: object, **kwargs: object) -> None:
            original(runner, *args, **kwargs)
            progress, tick = kwargs.get("on_progress"), kwargs.get("on_tick")
            assert callable(progress)
            assert callable(tick)
            progress(ProgressEvent("docs", "scanning", None, None))
            clock[0] = 165.0
            tick()
            refreshed.append(recorder.current)

        monkeypatch.setattr(Runner, "__init__", initialize)
        assert backup_cli._run_plan(cfg, plan, dry_run=False, plan_only=False, jobs=1) is False
        assert refreshed == ["docs scanning 1:05"]
        assert capability.closed == ["docs"]
        assert recorder.running is False

    @pytest.mark.parametrize("option", ["--quiet", "--list", "--show-excludes"])
    def test_cli_quiet_and_early_returns_never_create_live_status(
        self,
        tmp_path: Path,
        cli_display: tuple[StatusRecorder, StringIO],
        option: str,
    ) -> None:
        recorder, stream = cli_display
        source = tmp_path / "source"
        source.mkdir()
        (source / "payload").write_bytes(b"actual CLI archive")
        out = tmp_path / "result.tar.gz"
        config = tmp_path / "buvis-backup.yaml"
        config.write_text(
            json.dumps(
                {
                    "excludes": ["private-cache"],
                    "instances": {
                        "docs": {
                            "use": "tar-archive",
                            "with": {
                                "source": str(source),
                                "out": str(out),
                                "engine": "python-tarfile",
                            },
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        args = ["--config-dir", str(tmp_path), "--config", str(config)]
        args += [option, "docs"] if option == "--show-excludes" else ["--only", "docs", option]
        backup_cli.cli.main(args=args, standalone_mode=False)
        assert recorder.created == []
        assert out.exists() is (option == "--quiet")
        output = stream.getvalue()
        if option == "--quiet":
            assert str(out) in output
            assert output.splitlines()[-1].endswith("archived 1, skipped 0, failed 0")
        elif option == "--show-excludes":
            assert "private-cache" in output
        else:
            assert "docs" in output

    def test_cli_report_retries_pending_result_after_interrupt_without_duplicate_counts(
        self,
        cli_display: tuple[StatusRecorder, StringIO],
    ) -> None:
        _, stream = cli_display
        results = result_lines()
        assert backup_cli._report_steps(results) is True
        expected = stream.getvalue()
        stream.seek(0)
        stream.truncate()
        delivered: list[StepResult] = []
        interrupts: list[bool] = []

        def before_result(step: StepResult) -> None:
            delivered.append(step)
            if len(delivered) == 1:
                raise KeyboardInterrupt

        assert (
            backup_cli._report_steps(
                iter(results),
                on_interrupt=lambda: interrupts.append(True),
                on_result=before_result,
            )
            is True
        )
        assert delivered == [results[0], *results]
        assert interrupts == [True]
        assert stream.getvalue() == expected

    def test_cli_result_callback_error_is_surfaced_before_printing_result(
        self,
        cli_display: tuple[StatusRecorder, StringIO],
    ) -> None:
        _, stream = cli_display

        def fail_render(step: StepResult) -> None:
            raise RuntimeError(f"cannot render {step.label}")

        with pytest.raises(RuntimeError, match="cannot render docs-old"):
            backup_cli._report_steps([StepResult("docs-old", False, "not printed")], on_result=fail_render)
        assert "not printed" not in stream.getvalue()

    def test_cli_interrupted_live_run_closes_capability_and_status_before_exit_130(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cli_display: tuple[StatusRecorder, StringIO],
    ) -> None:
        recorder, stream = cli_display
        cfg, plan, capability = controlled_plan(monkeypatch, result_lines())
        recorder.interrupt = True
        with pytest.raises(SystemExit) as caught:
            backup_cli._run_plan(cfg, plan, dry_run=False, plan_only=False, jobs=1)
        assert caught.value.code == 130
        assert recorder.running is False
        assert recorder.created == [""]
        assert capability.closed
        assert set(capability.closed) <= {label for label, _ in plan}
        assert "interrupted:" in stream.getvalue()

    @pytest.mark.parametrize("tty,quiet", [(False, False), (True, True), (False, True)])
    def test_no_live_output_when_not_a_tty_or_quiet(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cli_display: tuple[StatusRecorder, StringIO],
        tty: bool,
        quiet: bool,
    ) -> None:
        recorder, stream = cli_display
        results = result_lines()
        cfg, plan, capability = controlled_plan(monkeypatch, results)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: tty)
        expected_failure = backup_cli._report_steps(results)
        expected = stream.getvalue()
        stream.seek(0)
        stream.truncate()
        failed = backup_cli._run_plan(cfg, plan, dry_run=False, plan_only=False, jobs=1, quiet=quiet)
        assert failed is expected_failure is True
        assert stream.getvalue() == expected
        for result in results:
            assert result.message in expected
        assert len(expected.splitlines()) > len(results)
        assert recorder.created == []
        assert sorted(capability.closed) == sorted(result.label for result in results)

    @pytest.mark.parametrize(
        "dry_run,plan_only,quiet,tty",
        [
            (False, False, True, True),
            (False, False, False, False),
            (True, False, False, True),
            (False, True, False, True),
        ],
    )
    def test_cli_disabled_modes_pass_no_progress_or_tick_callbacks_to_real_runner(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        cli_display: tuple[StatusRecorder, StringIO],
        dry_run: bool,
        plan_only: bool,
        quiet: bool,
        tty: bool,
    ) -> None:
        recorder, _ = cli_display
        source = tmp_path / "src"
        source.mkdir()
        (source / "payload").write_bytes(b"source bytes")
        out = tmp_path / "out.tar.gz"
        instance = BackupInstance(use="tar-archive", with_={"source": str(source), "out": str(out)})
        cfg = BackupConfig(instances={"docs": instance})
        calls: list[dict[str, object]] = []
        original = Runner.__init__

        def initialize(runner: Runner, *args: object, **kwargs: object) -> None:
            calls.append(kwargs)
            original(runner, *args, **kwargs)

        monkeypatch.setattr(Runner, "__init__", initialize)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: tty)
        assert (
            backup_cli._run_plan(
                cfg,
                [("docs", instance)],
                dry_run=dry_run,
                plan_only=plan_only,
                quiet=quiet,
            )
            is False
        )
        assert len(calls) == 1
        assert calls[0].get("on_progress") is None
        assert calls[0].get("on_tick") is None
        assert recorder.created == []
        assert out.exists() is (not dry_run and not plan_only)

    def test_cli_live_run_removes_completed_labels_before_each_final_line(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cli_display: tuple[StatusRecorder, StringIO],
    ) -> None:
        recorder, stream = cli_display
        results = result_lines()
        cfg, plan, capability = controlled_plan(monkeypatch, results)
        observations: list[tuple[str, str]] = []
        write = stream.write

        def observe_output(message: str) -> int:
            for result in results:
                if result.message in message:
                    observations.append((result.label, recorder.current if recorder.running else ""))
            return write(message)

        monkeypatch.setattr(stream, "write", observe_output)
        assert backup_cli._run_plan(cfg, plan, dry_run=False, plan_only=False, jobs=1) is True
        assert [label for label, _ in observations] == [result.label for result in results]
        for label, active in observations:
            assert label not in [part.split(" ", 1)[0] for part in active.split(" | ")]
        assert recorder.created == [""]
        assert recorder.running is False
        assert sorted(capability.closed) == sorted(result.label for result in results)
        output = stream.getvalue()
        for result in results:
            assert output.count(result.message) == 1

    @pytest.mark.parametrize("kind", ["empty", "preflight-failure", "no-progress"])
    def test_cli_live_run_without_active_events_never_creates_status(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cli_display: tuple[StatusRecorder, StringIO],
        kind: str,
    ) -> None:
        recorder, stream = cli_display
        results = [] if kind == "empty" else [StepResult("docs-old", False, "source unavailable")]
        cfg, plan, _ = controlled_plan(monkeypatch, results, progress=False)
        if kind == "preflight-failure":
            bad = BackupInstance(use="cli-progress-fixture-missing")
            cfg, plan = BackupConfig(instances={"docs": bad}), [("docs", bad)]
        assert backup_cli._run_plan(cfg, plan, dry_run=False, plan_only=False) is (kind != "empty")
        assert recorder.created == []
        assert recorder.running is False
        if kind == "no-progress":
            assert "source unavailable" in stream.getvalue()
