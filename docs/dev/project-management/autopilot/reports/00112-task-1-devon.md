Proved **8 weaknesses**. Every independent mutant passed all 17 tests. Original `step_result.py` restored byte-for-byte; SHA-256: `210e1177216a00fa002ff7b9adefa8f831686f3e0536fa716e070778e7447bdb`. No tests changed or files retained.

Runner used once per mutant:

```bash
uv run pytest tests/tools/backup/test_progress.py -k "event_record" -q --tb=line
```

Passing output:

```text
1: 17 passed in 0.02s
2: 17 passed in 0.01s
3: 17 passed in 0.01s
4: 17 passed in 0.01s
5: 17 passed in 0.01s
6: 17 passed in 0.01s
7: 17 passed in 0.01s
8: 17 passed in 0.01s
```

Mutants 1–5 and 7–8 independently started with the public declaration:

```python
from typing import Literal, NamedTuple

class ProgressEvent(NamedTuple):
    label: str
    phase: Literal["scanning", "archiving", "finalizing"]
    done_bytes: int | None
    total_bytes: int | None
```

Each then applied its following wrong implementation.

```python
# 1: Discard non-ASCII label characters.
_progress_new = ProgressEvent.__new__
def _wrong_new(cls, label, phase, done_bytes, total_bytes):
    return _progress_new(
        cls, label.encode("ascii", "ignore").decode(),
        phase, done_bytes, total_bytes,
    )
ProgressEvent.__new__ = _wrong_new
```

```python
# 2: Silently truncate large input sizes.
_progress_new = ProgressEvent.__new__
def _wrong_new(cls, label, phase, done_bytes, total_bytes):
    mask = (1 << 63) - 1
    return _progress_new(
        cls, label, phase,
        None if done_bytes is None else done_bytes & mask,
        None if total_bytes is None else total_bytes & mask,
    )
ProgressEvent.__new__ = _wrong_new
```

```python
# 3: Violate positional field order when indexed.
def _wrong_getitem(self, index):
    return tuple.__getitem__(self, 1 if index == 0 else index)
ProgressEvent.__getitem__ = _wrong_getitem
```

```python
# 4: Ignore label replacement.
_progress_replace = ProgressEvent._replace
def _wrong_replace(self, **changes):
    changes.pop("label", None)
    return _progress_replace(self, **changes)
ProgressEvent._replace = _wrong_replace
```

```python
# 5: Reject valid mixed positional/keyword construction.
_progress_new = ProgressEvent.__new__
def _wrong_new(cls, *args, **kwargs):
    if args and kwargs:
        raise TypeError("mixed construction unsupported")
    return _progress_new(cls, *args, **kwargs)
ProgressEvent.__new__ = _wrong_new
```

Mutant 6 replaced the declaration:

```python
from typing import Literal

class ProgressEvent(tuple):
    label: str
    phase: Literal["scanning", "archiving", "finalizing"]
    done_bytes: int | None
    total_bytes: int | None

    _fields = ("label", "phase", "done_bytes", "total_bytes")
    _field_defaults = {}

    def __new__(cls, label, phase, done_bytes, total_bytes):
        values = (label, phase, done_bytes, total_bytes)
        event = tuple.__new__(cls, values)
        event.__dict__["values"] = list(values)
        return event

    label = property(lambda self: self.__dict__["values"][0])
    phase = property(lambda self: self.__dict__["values"][1])
    done_bytes = property(lambda self: self.__dict__["values"][2])
    total_bytes = property(lambda self: self.__dict__["values"][3])

    def _replace(self, **changes):
        return type(self)(*(
            changes.get(field, value)
            for field, value in zip(self._fields, tuple(self))
        ))
```

```python
# 7: Share label state across all instances.
_progress_new = ProgressEvent.__new__
_progress_last_label = ""

def _wrong_new(cls, label, phase, done_bytes, total_bytes):
    global _progress_last_label
    _progress_last_label = label
    return _progress_new(cls, label, phase, done_bytes, total_bytes)

ProgressEvent.__new__ = _wrong_new
ProgressEvent.label = property(lambda self: _progress_last_label)
```

```python
# 8: Convert unknown sizes into zero during replacement.
_progress_replace = ProgressEvent._replace
def _wrong_replace(self, **changes):
    for field in ("done_bytes", "total_bytes"):
        if changes.get(field, getattr(self, field)) is None:
            changes[field] = 0
    return _progress_replace(self, **changes)
ProgressEvent._replace = _wrong_replace
```

Weak points:

1. `test_event_record_preserves_each_positional_field_and_byte_value` — Unicode labels are silently corrupted — add a Unicode label and assert exact preservation.
2. `test_event_record_preserves_each_positional_field_and_byte_value` — integers above signed 64-bit range are truncated — assert preservation of `2**63` and `2**80`.
3. `test_event_record_preserves_each_positional_field_and_byte_value` — indexed field order is wrong despite correct iteration — assert `event[0] == event.label` and each remaining index.
4. `test_event_record_crosses_worker_thread_without_sharing_mutable_call_state` — `_replace(label=...)` silently does nothing — replace each field independently and assert the resulting attributes.
5. `test_event_record_preserves_each_positional_field_and_byte_value` — valid mixed argument construction raises — assert `ProgressEvent("documents", phase="scanning", done_bytes=None, total_bytes=None)` equals its positional equivalent.
6. `test_event_record_rejects_field_mutation` — mutable `event.__dict__["values"]` changes field attributes despite blocked assignment — assert instances have no `__dict__`.
7. `test_event_record_crosses_worker_thread_without_sharing_mutable_call_state` — constructing another record changes an earlier record’s label attribute — construct differently labelled records across threads and reassert every original attribute.
8. `test_event_record_crosses_worker_thread_without_sharing_mutable_call_state` — `_replace` destroys unknown byte counts — assert phase-only replacement preserves `None`, and explicit replacement with `None` remains `None`.