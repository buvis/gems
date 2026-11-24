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
