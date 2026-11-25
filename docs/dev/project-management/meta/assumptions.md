# Assumptions ledger: 00151-bim-tiromex-backends-v1

## 1: llm layer foundation: base types, per-kind settings, registry

- Tess: the `require_strict_schema` JSON pointer goes through the pydantic `$defs` key, so the message names the child class; pointer syntax not asserted.
- Tess: a dict or list passed to `parse_json_text` is "not a str" and maps to PARSE (later extended to bytes after Pat's LOW).
- Tess: `build_registry` looks up `build_backend` as a module global at call time, so a monkeypatch takes effect.
- Ivan: `wire_schema` included in base.py although no task-1 test covers it (design lists it).
- Ivan: JSON pointer is a URI fragment (`#`, `#/$defs/_LooseLine`) with RFC 6901 escaping; the walk reports the first open object in the order $defs, properties, items, additionalProperties, anyOf, oneOf, allOf, prefixItems.
## 2-4: HTTP, command and Claude adapters

- Orchestrator: command and Claude adapter tests live in tests/tools/bim/test_llm_command.py and test_llm_claude.py (the PRD acceptance commands name test_llm_backends.py, which is near the 800-line limit); `-k command` / `-k claude` selection unchanged.
- Ivan (HTTP): `build_chat_request` omits `model` when None for every kind; detail texts carry suffixes after the pinned prefixes; the worker catches Exception, so a BaseException inside it surfaces as a deadline timeout.
- Ivan (runner): unpinned detail wording ("no reply within {timeout} seconds", "exited with code {rc}: ...", "pipe error: ..."); error precedence timeout > pipe still open > overflow > pipe error > non-zero exit > UTF-8 decode.
- Ivan (Claude): `is_error` without a string result reads "claude reported an error without a message"; an empty-string model sends no `--model`.
- Orchestrator: the live Claude probe could not authenticate in the sandbox, so the success-envelope key (`structured_output` vs `result`) is unverified; both are read. Re-run with a working login before 00153 qualifies Claude live.
- Orchestrator: run_cli falls back to a stdout excerpt when a non-zero exit has empty stderr (the claude CLI reports failures only on stdout).

## 1 (continued)

- Orchestrator (task 1 review): `parse_json_text` rejects bytes/bytearray as PARSE (Pat LOW, fixed in fe9fa1be).
- Orchestrator: `build_backend` uses an importlib table (see also task 3) instead of per-branch imports so mypy passes before the adapter modules exist; PLR0913 per-file-ignore added for registry.py because the design pins `invoke`'s signature.

## 8: [D1] llm transport hardening (review cycle 1 rework)

- Tess: `run_cli` starts exactly three threads (one stdin writer, two readers); the thread-start test fails call 1, 2 and 3.
- Tess: "the redirect body was not downloaded" is asserted as server bytes sent < 16 MiB, not as < `MAX_REPLY_BYTES` (the kernel buffers some unread bytes).
- Tess: a child cwd different from `tmp_path` counts as "runs in a fresh temp dir"; emptiness and removal are not checked.
- Ivan: a real `requests` is detected by `isinstance(getattr(requests, "Session", None), type)`; the existing test fakes expose only `post`, so `_post` falls back to `requests.post` for them. Pat (LOW): the fallback is dead code with real Requests; removing it needs the fakes in six test files to expose a `Session` class.
- Ivan: `session.get_redirect_target` is replaced on the instance, not by a `Session` subclass (mypy rejects the dynamic base class).
- Ivan: after a thread-start failure the child's pipes are not closed by hand; the process-group kill closes them.
- Orchestrator: the fix commit is typed `fix` with no CHANGELOG entry, because the feature is unreleased and its entry already exists.

## 10: [D1] doc CLI passes the llm map (review cycle 1 rework)

- Ivan: a non-empty named `llm` map needs `doc.classifier.backend` set to the entry name, or `BimSettings` validation rejects it.
