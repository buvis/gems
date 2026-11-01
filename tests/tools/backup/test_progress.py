from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Literal, get_type_hints

import pytest

from backup.step_result import ProgressEvent


class TestProgressEventRecord:
    def test_event_record_has_exact_named_tuple_fields_types_and_no_defaults(self) -> None:
        assert ProgressEvent.__bases__ == (tuple,)
        assert ProgressEvent._fields == ("label", "phase", "done_bytes", "total_bytes")
        assert ProgressEvent._field_defaults == {}
        assert get_type_hints(ProgressEvent) == {
            "label": str,
            "phase": Literal["scanning", "archiving", "finalizing"],
            "done_bytes": int | None,
            "total_bytes": int | None,
        }

    @pytest.mark.parametrize(
        "label,phase,done_bytes,total_bytes",
        [
            ("documents", "scanning", None, None),
            ("documents-old", "archiving", 37, 101),
            ("", "finalizing", 0, 0),
            ("photos", "archiving", 2**40, 2**41),
            ("photos", "scanning", 0, None),
            ("documents", "finalizing", None, 101),
        ],
    )
    def test_event_record_preserves_each_positional_field_and_byte_value(
        self,
        label: str,
        phase: Literal["scanning", "archiving", "finalizing"],
        done_bytes: int | None,
        total_bytes: int | None,
    ) -> None:
        event = ProgressEvent(label, phase, done_bytes, total_bytes)
        assert event.label == label
        assert event.phase == phase
        assert event.done_bytes == done_bytes
        assert event.total_bytes == total_bytes
        assert tuple(event) == (label, phase, done_bytes, total_bytes)
        assert event == ProgressEvent(
            total_bytes=total_bytes,
            done_bytes=done_bytes,
            phase=phase,
            label=label,
        )

    @pytest.mark.parametrize("field", ["label", "phase", "done_bytes", "total_bytes"])
    def test_event_record_rejects_field_mutation(self, field: str) -> None:
        event = ProgressEvent("documents", "archiving", 37, 101)
        with pytest.raises(AttributeError):
            setattr(event, field, None)
        assert tuple(event) == ("documents", "archiving", 37, 101)

    @pytest.mark.parametrize(
        "args",
        [(), ("documents",), ("documents", "scanning"), ("documents", "scanning", None)],
    )
    def test_event_record_requires_all_four_arguments(self, args: tuple[object, ...]) -> None:
        with pytest.raises(TypeError):
            ProgressEvent(*args)

    def test_event_record_distinguishes_similar_labels_and_each_field(self) -> None:
        event = ProgressEvent("documents", "archiving", 37, 101)
        assert event != ProgressEvent("documents-old", "archiving", 37, 101)
        assert event != ProgressEvent("documents", "finalizing", 37, 101)
        assert event != ProgressEvent("documents", "archiving", 38, 101)
        assert event != ProgressEvent("documents", "archiving", 37, 102)

    def test_event_record_crosses_worker_thread_without_sharing_mutable_call_state(self) -> None:
        original = ProgressEvent("documents", "scanning", None, None)
        with ThreadPoolExecutor(max_workers=1) as executor:
            updated = executor.submit(
                lambda event: event._replace(phase="archiving", done_bytes=37, total_bytes=101),
                original,
            ).result(timeout=5)
        assert tuple(original) == ("documents", "scanning", None, None)
        assert isinstance(updated, ProgressEvent)
        assert tuple(updated) == ("documents", "archiving", 37, 101)
