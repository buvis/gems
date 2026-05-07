"""Unit tests for the doc-ingest progress reporters.

The pipeline-level integration test (a recording reporter that captures the
ordered ``stage()`` calls during a real ``Pipeline.run``) lives in
``test_pipeline.py`` so it can reuse the existing pipeline-build helpers.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from bim.commands.doc.shared.progress import (
    NoOpProgressReporter,
    SpinnerProgressReporter,
)


class TestNoOpProgressReporter:
    def test_stage_returns_none_and_swallows_message(self) -> None:
        reporter = NoOpProgressReporter()
        # Must accept any string and produce no observable output.
        assert reporter.stage("running OCR") is None
        assert reporter.stage("anything else") is None

    def test_context_manager_protocol_round_trip(self) -> None:
        # Pipeline tests pass the no-op as the default; the CLI handler also
        # uses it as the batch-mode reporter inside ``with reporter:``.
        with NoOpProgressReporter() as r:
            assert isinstance(r, NoOpProgressReporter)
            r.stage("inside")


class TestSpinnerProgressReporter:
    def test_enter_starts_console_status_and_exit_stops_it(self) -> None:
        # The spinner reporter delegates to ``ConsoleAdapter.status()`` which
        # returns a Rich ``Status`` context manager. We mock the adapter so the
        # test stays isolated from Rich internals.
        fake_status = MagicMock()
        fake_console = MagicMock()
        fake_console.status.return_value = fake_status

        with SpinnerProgressReporter(fake_console):
            fake_console.status.assert_called_once_with("starting…")
            fake_status.__enter__.assert_called_once()

        # On exit, the underlying status' __exit__ must be invoked exactly
        # once so the spinner stops cleanly.
        assert fake_status.__exit__.call_count == 1

    def test_stage_updates_status_label_with_ellipsis(self) -> None:
        fake_status = MagicMock()
        fake_console = MagicMock()
        fake_console.status.return_value = fake_status

        with SpinnerProgressReporter(fake_console) as reporter:
            reporter.stage("running OCR")
            reporter.stage("classifying document")

        # Spec: each .stage() updates the spinner label in place (no new line).
        fake_status.update.assert_any_call("running OCR…")
        fake_status.update.assert_any_call("classifying document…")
        assert fake_status.update.call_count == 2

    def test_stage_outside_context_is_a_silent_noop(self) -> None:
        # Defensive: if .stage() is called before __enter__ (or after __exit__)
        # the reporter should not crash. A misbehaving caller is preferable to
        # taking down the pipeline run.
        fake_console = MagicMock()
        reporter = SpinnerProgressReporter(fake_console)
        reporter.stage("nothing yet")
        fake_console.status.assert_not_called()

    def test_exit_clears_status_so_reuse_does_not_double_stop(self) -> None:
        # Calling __exit__ twice must not double-call the underlying Status'
        # __exit__ — once the spinner is torn down it should not be touched.
        fake_status = MagicMock()
        fake_console = MagicMock()
        fake_console.status.return_value = fake_status

        reporter = SpinnerProgressReporter(fake_console)
        reporter.__enter__()
        reporter.__exit__(None, None, None)
        reporter.__exit__(None, None, None)

        assert fake_status.__exit__.call_count == 1


class TestProtocolCompliance:
    def test_no_op_satisfies_protocol_at_runtime(self) -> None:
        # Smoke test: structural typing means this is mainly a regression
        # guard against accidental signature drift in either implementation.
        from bim.commands.doc.shared.progress import ProgressReporter

        reporters: list[Any] = [NoOpProgressReporter(), SpinnerProgressReporter(MagicMock())]
        for r in reporters:
            assert hasattr(r, "stage")
            assert hasattr(r, "__enter__")
            assert hasattr(r, "__exit__")
        # Reference the protocol so the import is meaningful for static checkers.
        assert ProgressReporter is not None
