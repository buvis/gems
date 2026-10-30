from __future__ import annotations

import importlib
import json
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner

from backup.capabilities.tar_archive import ArchiveCancelled
from backup.cli import _report_steps, _run_plan, cli
from backup.step_result import StepResult
from tests.tools.backup.parallel_runner_helpers import WAIT, CapabilityProbe, configure

cli_module = importlib.import_module("backup.cli")
Transcript = list[tuple[str, str]]


def _capture_console(
    monkeypatch: pytest.MonkeyPatch,
    transcript: Transcript,
    interrupt: Callable[[str, str], None] | None = None,
) -> None:
    def sink(level: str) -> Callable[..., None]:
        def render(message: object = "", *args: object, **kwargs: object) -> None:
            line = str(message)
            if interrupt is not None:
                interrupt(level, line)
            transcript.append((level, line))

        return render

    for level in ("info", "success", "warning", "failure"):
        monkeypatch.setattr(getattr(cli_module, "console"), level, sink(level))


def _rows() -> list[StepResult]:
    return [StepResult("alpha", True, "published alpha"), StepResult("alpha-copy", False, "failed alpha-copy")]


@pytest.mark.parametrize("target", ["step", "summary"])
@pytest.mark.parametrize("repetitions", [1, 2])
@pytest.mark.parametrize("skipped", [False, True])
def test_cli_report_retries_interrupted_render_without_losing_steps_or_double_counting(
    monkeypatch: pytest.MonkeyPatch, target: str, repetitions: int, skipped: bool
) -> None:
    rows = _rows()
    expected: Transcript = [("success", "published alpha"), ("failure", "failed alpha-copy")]
    if skipped:
        rows.append(StepResult("omega", True, "skipped omega", skipped=True))
        expected.append(("warning", "skipped omega"))
    expected.append(("info", f"archived 1, skipped {int(skipped)}, failed 1"))
    interrupted_line = expected[0] if target == "step" else expected[-1]
    observed: Transcript = []
    cancellations: list[str] = []
    attempts = 0

    def interrupt(level: str, line: str) -> None:
        nonlocal attempts
        if (level, line) == interrupted_line and attempts < repetitions:
            attempts += 1
            raise KeyboardInterrupt

    _capture_console(monkeypatch, observed, interrupt)
    assert _report_steps(iter(rows), on_interrupt=lambda: cancellations.append("cancel")) is True
    assert observed == expected
    assert cancellations == ["cancel"] * repetitions
    assert attempts == repetitions


@pytest.mark.parametrize("empty", [False, True])
def test_cli_report_empty_or_successful_run_returns_false_and_propagates_interrupt_without_callback(
    monkeypatch: pytest.MonkeyPatch, empty: bool
) -> None:
    transcript: Transcript = []
    _capture_console(monkeypatch, transcript)
    rows = [] if empty else [StepResult("alpha", True, "ok alpha"), StepResult("omega", True, "ok omega")]
    assert _report_steps(iter(rows)) is False

    steps = _InterruptedInput(iter(rows), 1)
    with pytest.raises(KeyboardInterrupt):
        _report_steps(steps)


class _InterruptedInput:
    def __init__(self, rows: Iterator[StepResult], interruptions: int) -> None:
        self.rows = rows
        self.interruptions = interruptions

    def __iter__(self) -> _InterruptedInput:
        return self

    def __next__(self) -> StepResult:
        if self.interruptions:
            self.interruptions -= 1
            raise KeyboardInterrupt
        return next(self.rows)


@pytest.mark.parametrize("empty", [False, True])
def test_cli_report_drains_same_iterator_after_repeated_interrupts_while_fetching(
    monkeypatch: pytest.MonkeyPatch, empty: bool
) -> None:
    rows = [] if empty else [StepResult("alpha", True, "ok alpha"), StepResult("omega", True, "ok omega")]
    baseline: Transcript = []
    _capture_console(monkeypatch, baseline)
    assert _report_steps(iter(rows)) is False
    transcript: Transcript = []
    _capture_console(monkeypatch, transcript)
    cancelled: list[bool] = []
    steps = _InterruptedInput(iter(rows), 2)
    assert _report_steps(steps, on_interrupt=lambda: cancelled.append(True)) is False
    assert transcript == baseline
    assert cancelled == [True, True]
    assert list(steps) == []


def _interruptible_probe() -> tuple[CapabilityProbe, threading.Event]:
    probe = CapabilityProbe(("alpha", "alpha-copy", "omega"))
    cleaned = threading.Event()

    def behavior(kwargs: dict[str, object]) -> Iterator[StepResult]:
        name = str(kwargs["label"])
        if name == "alpha":
            assert probe.started["alpha-copy"].wait(WAIT)
            yield StepResult(name, True, "published alpha")
            return
        cancel = kwargs["cancel"]
        assert isinstance(cancel, threading.Event)
        assert cancel.wait(WAIT)
        cleaned.set()
        raise ArchiveCancelled()

    probe.behavior = behavior
    return probe, cleaned


@pytest.mark.parametrize("repetitions", [1, 2])
def test_cli_interrupt_retries_published_step_drains_workers_and_retries_exit_130_message(
    monkeypatch: pytest.MonkeyPatch, repetitions: int
) -> None:
    probe, cleaned = _interruptible_probe()
    cfg = configure(monkeypatch, probe)
    transcript: Transcript = []
    attempts = {"step": 0, "final": 0}

    def interrupt(level: str, line: str) -> None:
        target = "step" if "published alpha" in line else "final" if line.startswith("interrupted:") else ""
        if target and attempts[target] < repetitions:
            attempts[target] += 1
            raise KeyboardInterrupt

    _capture_console(monkeypatch, transcript, interrupt)
    with pytest.raises(SystemExit) as exc:
        _run_plan(cfg, list(cfg.instances.items()), dry_run=False, plan_only=False, jobs=2)
    assert exc.value.code == 130
    assert cleaned.is_set()
    assert probe.active == 0
    assert not probe.started["omega"].is_set()
    assert sum("published alpha" in line for _, line in transcript) == 1
    assert any("alpha-copy" in line and not line.startswith("interrupted:") for _, line in transcript)
    assert any("omega" in line and not line.startswith("interrupted:") for _, line in transcript)
    assert transcript[-1] == ("failure", "interrupted: alpha-copy, omega")
    assert attempts == {"step": repetitions, "final": repetitions}


@pytest.mark.parametrize("target", ["step", "summary"])
def test_cli_interrupt_after_completed_work_reports_no_unfinished_instances(
    monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    probe = CapabilityProbe(("alpha",))
    probe.release_all()
    cfg = configure(monkeypatch, probe)
    baseline: Transcript = []
    _capture_console(monkeypatch, baseline)
    assert _report_steps(iter([StepResult("alpha", True, "complete alpha")])) is False
    interrupted_line = baseline[0] if target == "step" else baseline[-1]
    transcript: Transcript = []
    attempts = 0

    def interrupt(level: str, line: str) -> None:
        nonlocal attempts
        if (level, line) == interrupted_line and attempts < 2:
            attempts += 1
            raise KeyboardInterrupt

    _capture_console(monkeypatch, transcript, interrupt)
    with pytest.raises(SystemExit) as exc:
        _run_plan(cfg, list(cfg.instances.items()), dry_run=False, plan_only=False, jobs=1)
    assert exc.value.code == 130
    assert attempts == 2
    assert transcript[:-1] == baseline
    assert transcript[-1] == ("failure", "interrupted: no unfinished instances")
    assert probe.active == 0
    assert len(probe.calls) == 1


def test_cli_unrelated_render_exception_closes_generator_and_joins_active_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe, cleaned = _interruptible_probe()
    cfg = configure(monkeypatch, probe)

    def fail_render(level: str, line: str) -> None:
        if "published alpha" in line:
            raise ValueError("console unavailable")

    _capture_console(monkeypatch, [], fail_render)
    with pytest.raises(ValueError, match="console unavailable"):
        _run_plan(cfg, list(cfg.instances.items()), dry_run=False, plan_only=False, jobs=2)
    assert cleaned.is_set()
    assert probe.active == 0
    assert not probe.started["omega"].is_set()


@pytest.mark.parametrize(
    "names,failed,selector,expected",
    [
        (("alpha", "alpha-copy"), False, "", 0),
        (("alpha", "alpha-copy"), True, "", 1),
        (("alpha", "alpha-copy"), False, "alpha-copy", 0),
        (("alpha", "alpha-copy"), True, "alpha-copy", 1),
        (("alpha", "alpha-copy"), False, "alpha-cop", 1),
        ((), False, "", 0),
    ],
)
def test_cli_preserves_success_failure_and_unknown_selector_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    names: tuple[str, ...],
    failed: bool,
    selector: str,
    expected: int,
) -> None:
    probe = CapabilityProbe(names)
    cfg = configure(monkeypatch, probe)
    payload = cfg.model_dump(by_alias=True)
    payload["instances"]["git-src"] = {"use": "tar-archive", "enabled": False}
    path = tmp_path / "ordinary.yaml"
    path.write_text(json.dumps(payload), encoding="utf-8")

    def behavior(kwargs: dict[str, object]) -> Iterator[StepResult]:
        name = str(kwargs["label"])
        yield StepResult(name, not (failed and name == "alpha-copy"), f"outcome {name}")

    probe.behavior = behavior
    transcript: Transcript = []
    _capture_console(monkeypatch, transcript)
    selection = ["--only", selector] if selector else []
    result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(path), "--jobs", "2", *selection])
    assert result.exit_code == expected, (result.output, result.exception)
    selected = {name for name in names if not selector or name == selector}
    assert {row["label"] for row in probe.calls} == selected
    assert len(probe.calls) == len(selected)
    for name in selected:
        assert any(f"outcome {name}" in line for _, line in transcript)
    if selector == "alpha-cop":
        assert any(selector in line for _, line in transcript)
    assert not any(line.startswith("interrupted:") for _, line in transcript)
    assert probe.active == 0


def test_cli_loads_ordinary_yaml_and_keeps_standard_options_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = CapabilityProbe(("alpha",))
    configure(monkeypatch, probe)
    probe.release_all()
    path = tmp_path / "ordinary.yaml"
    path.write_text(
        "instances:\n"
        "  git-src:\n    use: tar-archive\n    enabled: false\n"
        "  alpha:\n    use: parallel-probe\n    with:\n"
        "      source: /source/alpha\n      out: /output/alpha.tgz\n      token: token-alpha\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(path)])
    assert result.exit_code == 0, (result.output, result.exception)
    assert len(probe.calls) == 1
    assert probe.calls[0]["source"] == "/source/alpha"
    assert probe.calls[0]["out"] == "/output/alpha.tgz"
    assert probe.calls[0]["token"] == "token-alpha"
    help_result = CliRunner().invoke(cli, ["--help"])
    assert help_result.exit_code == 0, help_result.output
    for option in ("--version", "--config", "--config-dir", "--log-level", "--debug", "--update", "--jobs"):
        assert option in help_result.output


def test_cli_rejects_unknown_capability_inputs_before_running_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = CapabilityProbe(("alpha",))
    cfg = configure(monkeypatch, probe)
    probe.release_all()
    payload = cfg.model_dump(by_alias=True)
    payload["instances"]["git-src"] = {"use": "tar-archive", "enabled": False}
    payload["instances"]["alpha"]["with"]["unsupported_input"] = "unexpected"
    path = tmp_path / "unknown-input.yaml"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(path)])
    assert result.exit_code == 1, (result.output, result.exception)
    assert "unsupported_input" in result.output
    assert probe.calls == []
