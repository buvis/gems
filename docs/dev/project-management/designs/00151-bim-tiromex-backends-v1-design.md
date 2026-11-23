# Design: 00151 bim shared schema-checked LLM backends

PRD: `docs/dev/project-management/prds/wip/00151-bim-tiromex-backends-v1.md`
Requirements source: discovery 00149, M18 to M21 and the "Config shape (decided)" section.

## Architecture fit

- The new layer lives in `src/tools/bim/shared/llm/`. It is tool-level shared code (bim only), not `src/lib/`: the discovery rule says the LLM layer stays under `src/tools/bim/` until it has a second consumer outside bim. `src/tools/bim/shared/` already holds bim-wide helpers (`suggest_tags.py`, `vault_links.py`), so a `llm/` package beside them fits the existing layout.
- The layer has no UI dependency and no console output. It raises `BackendError` (operational failure) and `LLMConfigError` (bad configuration). Command classes and the doc pipeline turn those into `CommandResult` / triage reasons; nothing in the layer calls `console`, `sys.exit` or `print`.
- Configuration: a new top-level `llm:` map on `BimSettings` (`src/tools/bim/settings.py`), keyed by backend name. `tx.backend` (already present, PRD 00150) and `doc.classifier.backend` / `doc.classifier.fallback` name entries in that map. tx does not call the layer in this PRD; ingest (00153) is the first tx caller.
- doc keeps its domain logic (prompts, field coercion, partial extraction, pinned fields, retry/fallback, triage). Only the transport moves: `Classifier` and `Extractor` stop calling `requests.post` themselves and call the shared registry. The composition root (`src/tools/bim/dependencies.py`) resolves which backend and model the doc pipeline uses.
- Port reference (read-only, never imported): `src/tools/klyreon/backends/{base,claude,stub}.py`. 00155 deletes klyreon; nothing here imports it.

## Module placement

New files:

- `src/tools/bim/shared/llm/__init__.py` - re-exports the public names listed in `## Interfaces & contracts` (explicit `__all__`). Imports only `base`, `settings`, `registry`; adapters load lazily.
- `src/tools/bim/shared/llm/base.py` - `BackendReason`, `BackendError`, `LLMConfigError`, `LLMRequest`, `Backend` protocol, `JsonObject`, `wire_schema`, `require_strict_schema`, `parse_json_text`, `validate_payload`, `MAX_REPLY_BYTES`, `MAX_STDERR_BYTES`, `run_cli` (the bounded subprocess runner both CLI adapters use).
- `src/tools/bim/shared/llm/settings.py` - per-kind pydantic entry models and the `LLMBackendSettings` discriminated union.
- `src/tools/bim/shared/llm/registry.py` - `LLMRegistry`, `build_backend`, `build_registry`.
- `src/tools/bim/shared/llm/http.py` - `HttpBackend`, `build_chat_request`, `read_chat_content` (Ollama, llama.cpp, OpenAI-compatible wire formats; the doc wire code moves here).
- `src/tools/bim/shared/llm/claude.py` - `ClaudeBackend` (port of klyreon's adapter, schema supplied by the caller).
- `src/tools/bim/shared/llm/command.py` - `CommandBackend` (generic argv driver).
- `tests/tools/bim/test_llm_registry.py`, `tests/tools/bim/test_llm_backends.py`.

Edited files:

- `src/tools/bim/commands/doc/shared/llm.py` - the chat wire functions move to `shared/llm/http.py`; this file now holds the doc route: `DocLLMTarget`, `DocLLMRoute`, `resolve_doc_route`, `DOC_REQUEST_TIMEOUT_SECONDS`, `LEGACY_DOC_BACKENDS`.
- `src/tools/bim/commands/doc/shared/settings_models.py` - `ClassifierSettings.backend` widens from `Literal["ollama", "llamacpp"]` to `str`; new `fallback: str | None = None`.
- `src/tools/bim/commands/doc/shared/classifier.py`, `extractor.py` - transport through the registry; error mapping below.
- `src/tools/bim/commands/doc/shared/health.py` - health per resolved backend kind.
- `src/tools/bim/commands/doc/shared/pipeline.py` - `PipelineServices.llm_route`; retry keys and `extraction_method` come from the route.
- `src/tools/bim/commands/doc/shared/pipeline_helpers.py` - no signature change (`retry_llm_call` stays string-keyed); listed in the PRD only because the keys it receives change meaning in named mode. Touch it only if a docstring names "model".
- `src/tools/bim/settings.py` - `llm` field and cross-reference validator.
- `src/tools/bim/dependencies.py` - `get_classifier`, `get_extractor`, `get_pipeline`, `get_health_checker` take the `llm` map.
- `src/tools/bim/doc_cli.py` - pass `settings.llm` to `get_pipeline` and to the health checker (6 call sites). Not in the PRD's file list; needed because the CLI is where `BimSettings` meets `DocSettings`. Without it a named doc backend could never resolve.
- Tests: `tests/tools/bim/doc/test_llm.py` (rewritten against the moved wire functions and the doc route), `test_classifier.py`, `test_extractor.py`, `test_classifier_pinned.py`, `test_extractor_pinned.py`, `test_settings_models.py`, `test_dependencies.py`, `test_health.py`; `tests/tools/bim/test_settings.py` for the `llm` field.
- `docs/source/tools/bim.rst`, `CHANGELOG.md`.

## Interfaces & contracts

All modules start with `from __future__ import annotations`. Timeouts are seconds as `float`.

### `src/tools/bim/shared/llm/base.py`

```python
class BackendReason(str, Enum):
    TIMEOUT = "timeout"
    EXIT = "exit"
    PARSE = "parse"
    SCHEMA = "schema"

class BackendError(RuntimeError):
    def __init__(self, reason: BackendReason | str, detail: str, *, backend: str) -> None
    reason: BackendReason   # BackendReason(reason); an unknown string raises ValueError
    detail: str
    backend: str            # the registry name of the backend that failed
    # str(exc) == f"[{reason.value}] {backend}: {detail}"

class LLMConfigError(ValueError):
    """Unknown backend name, unattended refusal, or a schema type that does not forbid extra keys."""

@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system: str | None = None
    def as_text(self) -> str  # system + "\n\n" + prompt when system is set, else prompt (stdin for CLI backends)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

class JsonObject(RootModel[dict[str, Any]]):
    """Any JSON object. For callers (doc) that coerce fields themselves."""

@runtime_checkable
class Backend(Protocol):
    name: str
    unattended_safe: bool
    def complete(self, request: LLMRequest, schema: type[SchemaT], *, timeout: float, model: str | None = None) -> SchemaT: ...

def wire_schema(schema: type[BaseModel]) -> dict[str, Any]
    # {"type": "object"} for JsonObject (or a subclass); schema.model_json_schema() otherwise
def require_strict_schema(schema: type[BaseModel]) -> None
    # JsonObject (or subclass): accepted as is.
    # Otherwise walks schema.model_json_schema() recursively (root, "$defs", "properties", "items",
    # "anyOf"/"oneOf"/"allOf", "prefixItems"); every node that has a "properties" key must also have
    # "additionalProperties": False (what pydantic emits for extra="forbid"). A node without "properties"
    # whose "additionalProperties" is a schema (an explicit dict[str, X] field) is an open mapping and allowed.
    # Any violation -> LLMConfigError(f"schema {schema.__name__} allows unexpected keys at {json_pointer}; set extra='forbid'")

MAX_REPLY_BYTES = 4 * 1024 * 1024     # cap on an HTTP body or a CLI stdout
MAX_STDERR_BYTES = 64 * 1024          # cap on CLI stderr kept for diagnostics
def parse_json_text(text: object, *, backend: str) -> Any
    # json.loads; JSONDecodeError or TypeError (text is not a str, e.g. a null "content")
    #   -> BackendError(PARSE, f"reply is not valid JSON: {exc}", backend=backend)
def validate_payload(schema: type[SchemaT], data: Any, *, backend: str) -> SchemaT
    # schema.model_validate(data); ValidationError -> BackendError(SCHEMA, f"reply does not match {schema.__name__}: {exc}", backend=backend)
```

Rules:

- Every adapter failure is a `BackendError` with one of the four reasons. Nothing else escapes `complete()` except `LLMConfigError` raised before any I/O. `KeyboardInterrupt` is never caught.
- `BackendError` is operational, not control flow: commands catch it and return `CommandResult(success=False, error=str(exc))`; doc maps it per the doc table below.
- The test stub is not a backend kind. Tests pass their own `Backend` implementations to `LLMRegistry(...)`; no config value can select a stub.

### `src/tools/bim/shared/llm/settings.py`

```python
class ClaudeBackendSettings(BaseModel):   # model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["claude"]
    model: str | None = None

class HttpBackendSettings(BaseModel):     # frozen, extra="forbid"
    kind: Literal["ollama", "llamacpp", "openai"]
    endpoint: str                          # base URL; trailing "/" stripped at use
    model: str | None = None

class CommandBackendSettings(BaseModel):  # frozen, extra="forbid"
    kind: Literal["command"]
    argv: list[str] = Field(min_length=1)  # each element non-empty (field_validator)
    unattended: bool = False

LLMBackendSettings = Annotated[
    ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings,
    Field(discriminator="kind"),
]
```

- An unknown `kind`, a missing required key (`endpoint` for HTTP kinds, `argv` for `command`) or a key that belongs to another kind (e.g. `argv` on a `claude` entry) is a pydantic `ValidationError` at config load.
- `ollama` and `openai` need a model per call: `HttpBackend.complete` raises `LLMConfigError(f"backend {name!r} has no model; set llm.{name}.model")` when both the call-time `model` and `settings.model` are `None`. `llamacpp` may run without a model (llama-server serves the model it was started with); the request body then omits `"model"`.

### `src/tools/bim/shared/llm/registry.py`

```python
class LLMRegistry:
    def __init__(self, backends: Mapping[str, Backend]) -> None
    def names(self) -> frozenset[str]
    def get(self, name: str, *, unattended: bool = False) -> Backend
        # unknown name -> LLMConfigError(f"unknown LLM backend {name!r}; configured: {sorted(names)}")
        # unattended and not backend.unattended_safe ->
        #   LLMConfigError(f"backend {name!r} cannot run unattended: a command backend cannot prove its tools are off; set llm.{name}.unattended: true to accept that risk")
    def invoke(self, name: str, request: LLMRequest, schema: type[SchemaT], *, timeout: float,
               model: str | None = None, unattended: bool = False) -> SchemaT
        # require_strict_schema(schema); self.get(name, unattended=unattended).complete(request, schema, timeout=timeout, model=model)

def build_backend(name: str, settings: ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings) -> Backend
    # dispatches on settings.kind; imports claude/command/http adapter modules inside the function
def build_registry(llm: Mapping[str, ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings]) -> LLMRegistry
```

`unattended_safe`: `ClaudeBackend` True (it passes `--tools ""`), `HttpBackend` True (an HTTP chat endpoint has no tool access), `CommandBackend` = `settings.unattended`. The scheduler (00154) passes `unattended=True`; interactive commands pass the default `False`.

### `src/tools/bim/shared/llm/http.py`

```python
def build_chat_request(kind: Literal["ollama", "llamacpp", "openai"], endpoint: str, model: str | None,
                       messages: list[dict[str, str]], schema: dict[str, Any]) -> tuple[str, dict[str, object]]
def read_chat_content(kind: Literal["ollama", "llamacpp", "openai"], payload: Any) -> str
    # KeyError/TypeError/IndexError on a malformed reply (empty "choices" raises KeyError("choices"));
    # a content value that is not a str (null, object) raises TypeError

class HttpBackend:
    def __init__(self, name: str, settings: HttpBackendSettings) -> None
    name: str
    unattended_safe = True
    def complete(self, request, schema, *, timeout, model=None)  # Backend protocol
```

Wire formats (byte-compatible with today's `bim doc` for `ollama` and `llamacpp`):

- `ollama`: `POST {endpoint}/api/chat`, body `{"model": m, "messages": msgs, "format": "json", "stream": False}`; reply text `payload["message"]["content"]`.
- `llamacpp`: `POST {endpoint}/v1/chat/completions`, body `{"model": m (omitted when None), "messages": msgs, "response_format": {"type": "json_schema", "json_schema": {"name": "reply", "schema": schema}}, "chat_template_kwargs": {"enable_thinking": False}, "stream": False}`; reply text `payload["choices"][0]["message"]["content"]`.
- `openai`: same URL, body and reply path as `llamacpp` but without `chat_template_kwargs` (a strict OpenAI-compatible server may reject unknown keys).
- `schema` is `wire_schema(caller_schema)`, so doc (which passes `JsonObject`) still sends `{"type": "object"}`.
- Messages: `[{"role": "system", "content": request.system}]` when `system` is set, then `[{"role": "user", "content": request.prompt}]`.

Transport: `import requests` inside `complete` (lazy; the `[doc]` extra and `jira` via `[bim]` both install it; no new dependency). The call runs in a worker: `concurrent.futures.ThreadPoolExecutor(max_workers=1)` per call, `future.result(timeout=timeout)` in the caller; on `concurrent.futures.TimeoutError` the caller sets a `threading.Event` `cancelled`, calls `executor.shutdown(wait=False)` and raises `timeout`. So the caller is released at the total deadline whatever the server does (headers, body, trickle). The worker: `requests.post(url, json=body, timeout=timeout, stream=True, allow_redirects=False)`; a 3xx status -> `exit` (`redirect not followed`), so no redirect body is ever read; `response.raise_for_status()`; the body is read with `response.iter_content(chunk_size=8192)` into a buffer, stopping when `cancelled` is set and failing with `exit` (`reply larger than {MAX_REPLY_BYTES} bytes`) as soon as the buffer passes `MAX_REPLY_BYTES`; `response.close()` in `finally`. Residual, accepted: after a deadline the worker thread can stay blocked in one socket read until `requests`' per-read `timeout` fires; it holds at most `MAX_REPLY_BYTES` and one connection, and the endpoint is one the user configured. The envelope is `json.loads(buffer)`. Doc test fakes gain an `iter_content` method returning the encoded JSON body; assertions stay.

Error mapping (`HttpBackend.complete`):

| failure | reason | detail starts with |
|---|---|---|
| `ImportError` on `import requests` | `exit` | `the 'requests' package is not installed` |
| `requests.exceptions.Timeout` | `timeout` | `no reply from {url} within {timeout}s` |
| any other exception from `post`, `raise_for_status()`, reading the body, or decoding the envelope (`UnicodeDecodeError`, `JSONDecodeError`) | `exit` | `HTTP error calling {url}: {exc}` |
| total deadline passed while reading the body | `timeout` | `no complete reply from {url} within {timeout}s` |
| body larger than `MAX_REPLY_BYTES` | `exit` | `reply larger than` |
| `read_chat_content` raises `KeyError`/`TypeError`/`IndexError` | `parse` | `malformed reply envelope: {exc}` |
| reply text is not JSON (`parse_json_text`) | `parse` | `reply is not valid JSON` |
| JSON does not validate (`validate_payload`) | `schema` | `reply does not match` |

An envelope decode failure stays `exit` on purpose: today `response.json()` failing is a transient transport failure in doc, and doc retries on `exit`.

### Subprocess runner (shared by `claude.py` and `command.py`, lives in `base.py`)

```python
def run_cli(argv: list[str], stdin_text: str, *, timeout: float, backend: str) -> str
    # returns decoded stdout of a zero-exit run, or raises BackendError
```

- `shutil.which(argv[0]) is None` -> `exit` (`{argv[0]!r} is not on PATH`), before spawning. (Claude's message names the claude CLI.)
- In a `tempfile.TemporaryDirectory(prefix="bim-llm-")` used as `cwd`: `proc = subprocess.Popen(argv, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=cwd, start_new_session=True)`; no shell, no files on disk.
- One writer thread writes `stdin_text.encode("utf-8")` and closes stdin (a `BrokenPipeError` is ignored; the exit code decides). Two reader threads drain stdout and stderr in 8192-byte reads into in-memory buffers: stdout keeps at most `MAX_REPLY_BYTES` and on overflow sets an `overflow` event and kills the process group; stderr keeps the first `MAX_STDERR_BYTES` and discards the rest while still draining. Memory is bounded by the two caps; nothing is written to disk.
- The caller waits with `proc.wait(timeout=timeout)`. `subprocess.TimeoutExpired` -> `os.killpg(proc.pid, signal.SIGKILL)` (the CLI and every descendant in its session), `proc.wait()`, then `timeout`. `OSError` from `Popen` -> `exit`.
- After any exit, `os.killpg(proc.pid, signal.SIGKILL)` once more, ignoring `ProcessLookupError`, so no descendant outlives the call and every pipe closes; the reader threads are then joined with a 5-second bound. (`start_new_session` drops the controlling tty; correct here, these CLIs are non-interactive. A descendant that calls `setsid` itself escapes the group; accepted, documented.)
- `overflow` set -> `exit` (`output larger than {MAX_REPLY_BYTES} bytes`).
- stderr decoded with `errors="replace"`; used only in messages (`stderr.strip()[:300]`).
- Non-zero return code -> `exit` with that stderr excerpt.
- stdout decoded as UTF-8 strictly; `UnicodeDecodeError` -> `parse` (`output is not UTF-8`).
- `KeyboardInterrupt` during `communicate` kills the process group in a `finally` and re-raises.

### `src/tools/bim/shared/llm/claude.py`

```python
CLAUDE_TIMEOUT_CUSHION_SECONDS = 30

class ClaudeBackend:
    def __init__(self, name: str, settings: ClaudeBackendSettings) -> None
    name: str
    unattended_safe = True
    def argv(self, schema: type[BaseModel], model: str | None) -> list[str]
        # ["claude", "-p", "--output-format", "json", "--json-schema", json.dumps(wire_schema(schema)),
        #  "--tools", "", "--strict-mcp-config", "--safe-mode", "--disable-slash-commands", "--no-session-persistence"]
        # + ["--model", m] when m = model or settings.model is set
    def complete(self, request, schema, *, timeout, model=None)
```

- Why each isolation flag (all in the installed `claude --help`, 2026-11-23): `--tools ""` removes the built-in tools; `--strict-mcp-config` with no `--mcp-config` loads no MCP server; `--safe-mode` disables CLAUDE.md, skills, installed plugins, hooks, MCP servers and custom agents while keeping normal auth (`--bare` is rejected because it accepts only `ANTHROPIC_API_KEY`, which breaks OAuth/setup-token users); `--disable-slash-commands` blocks skills invoked by name; `--no-session-persistence` stops each run writing a transcript. `unattended_safe = True` rests on this whole set; the `-k claude` tests pin the exact argv, so dropping a flag fails a test.
- Headless verification is part of the implementation task: run one probe `claude -p --output-format json --json-schema '{"type":"object"}' <the isolation flags> ` with the prompt `Reply with {"ok": true}` on stdin, from a temp dir, and record the CLI version, the date and the envelope keys seen (`structured_output` vs `result`) in `bim.rst`. If the installed CLI rejects one of the flags, the task stops and reports it (do not drop the flag silently).
- Runs `run_cli(self.argv(schema, model), request.as_text(), timeout=timeout + CLAUDE_TIMEOUT_CUSHION_SECONDS, backend=self.name)`; missing `claude` reads `the 'claude' CLI is not on PATH`.
- Envelope: `parse_json_text(stdout)` (`parse`). If the envelope is a dict with `is_error` true -> `exit` with its `result` text. Payload = `envelope["structured_output"]` when that key is present, else `envelope.get("result", envelope)` (a bare payload is accepted). A string payload is parsed once more with `parse_json_text` (`parse`). Then `validate_payload` (`schema`).

### `src/tools/bim/shared/llm/command.py`

```python
class CommandBackend:
    def __init__(self, name: str, settings: CommandBackendSettings) -> None
    name: str
    unattended_safe: bool   # = settings.unattended
    def complete(self, request, schema, *, timeout, model=None)   # model is ignored
```

- `argv` is passed literally as a list (no shell, no placeholder expansion, no prompt in argv): `run_cli(list(settings.argv), request.as_text(), timeout=timeout, backend=self.name)`; stdout -> `parse_json_text` (`parse`) -> `validate_payload` (`schema`).
- The docs and the `LLMConfigError` text never claim that a command backend runs without tools.

### `src/tools/bim/shared/llm/__init__.py`

`__all__ = ["Backend", "BackendError", "BackendReason", "ClaudeBackendSettings", "CommandBackendSettings", "HttpBackendSettings", "JsonObject", "LLMBackendSettings", "LLMConfigError", "LLMRegistry", "LLMRequest", "build_registry"]`

### Settings: `src/tools/bim/settings.py`

```python
class BimSettings(GlobalSettings):
    ...
    llm: dict[str, LLMBackendSettings] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _doc_backends_exist(self) -> BimSettings
        # when self.doc is not None: resolve_doc_route(self.doc.classifier, self.llm)
        # LLMConfigError is a ValueError, so pydantic reports it as a config ValidationError at load
```

`tx.backend` is not cross-checked here; 00153 adds that check when ingest first calls the registry (see Risks).

### Doc settings: `src/tools/bim/commands/doc/shared/settings_models.py`

```python
class ClassifierSettings(BaseModel):   # frozen, extra="forbid" (unchanged)
    backend: str = "ollama"            # was Literal["ollama", "llamacpp"]
    fallback: str | None = None        # new
    endpoint: str = "http://localhost:11434"
    primary_model: str = "qwen3:30b-a3b"
    fallback_model: str = "qwen3:14b"
    triage_threshold: float = 0.85
    max_retries: int = 2
```

`LLMSettings = ClassifierSettings` alias stays.

### Doc route: `src/tools/bim/commands/doc/shared/llm.py`

```python
LEGACY_DOC_BACKENDS: frozenset[str] = frozenset({"ollama", "llamacpp"})
DOC_REQUEST_TIMEOUT_SECONDS: float = 60

@dataclass(frozen=True)
class DocLLMTarget:
    backend: str          # registry name
    model: str | None     # call-time model override; None = the entry's own model
    key: str              # string the retry helper passes around; also the extraction_method suffix

@dataclass(frozen=True)
class DocLLMRoute:
    primary: DocLLMTarget
    fallback: DocLLMTarget
    legacy: bool
    backends: Mapping[str, ClaudeBackendSettings | HttpBackendSettings | CommandBackendSettings]
    def target(self, key: str) -> DocLLMTarget

def resolve_doc_route(classifier: ClassifierSettings, llm: Mapping[str, ...]) -> DocLLMRoute
```

`resolve_doc_route` rules:

1. `classifier.backend in llm` (named mode, `legacy=False`): primary = `DocLLMTarget(backend, None, key=backend)`. Fallback name = `classifier.fallback or classifier.backend`; it must be in `llm`, else `LLMConfigError(f"doc.classifier.fallback {name!r} is not an llm entry")`; fallback = `DocLLMTarget(fallback_name, None, key=fallback_name)`. `backends = dict(llm)`. `endpoint`, `primary_model`, `fallback_model` are ignored in this mode.
2. Else `classifier.backend in LEGACY_DOC_BACKENDS` (legacy mode, `legacy=True`): `classifier.fallback` must be `None`, else `LLMConfigError("doc.classifier.fallback needs doc.classifier.backend to name an llm entry")`. A synthetic entry `HttpBackendSettings(kind=classifier.backend, endpoint=classifier.endpoint)` is registered under the name `classifier.backend`. primary = `DocLLMTarget(classifier.backend, classifier.primary_model, key=classifier.primary_model)`; fallback = `DocLLMTarget(classifier.backend, classifier.fallback_model, key=classifier.fallback_model)`. `backends = {classifier.backend: synthetic}`.
3. Else: `LLMConfigError(f"doc.classifier.backend {classifier.backend!r} is neither an llm entry nor one of ['llamacpp', 'ollama']")`.

A named entry wins over the legacy meaning: an `llm:` entry called `ollama` is used as a named entry.

`DocLLMRoute.target(key)`: `fallback` when `key == fallback.key`; else `primary` when `key == primary.key`; else, in legacy mode only, `DocLLMTarget(primary.backend, key, key=key)` (today any model string a caller passes reaches the same endpoint); in named mode an unknown key raises `LLMConfigError`.

### Doc callers

```python
class Classifier:
    def __init__(self, settings: ClassifierSettings, *, llm: Mapping[str, ...] | None = None,
                 route: DocLLMRoute | None = None, registry: LLMRegistry | None = None) -> None
        # self._route = route or resolve_doc_route(settings, llm or {})
        # self._registry = registry or build_registry(self._route.backends)
class Extractor:
    def __init__(self, settings: LLMSettings, *, llm: Mapping[str, ...] | None = None,
                 route: DocLLMRoute | None = None, registry: LLMRegistry | None = None) -> None
```

`Classifier(settings)` / `Extractor(settings)` (how today's tests build them) still work and resolve the legacy route. `get_pipeline` passes the same `route` and `registry` objects to both, and the same `route` to `PipelineServices`, so retry keys and target lookup can never come from two separate resolutions.

Public method signatures (`classify`, `classify_with_model(model=...)`, `classify_with_pinned(model=...)`, `extract`, `extract_with_model(model=...)`, `extract_with_pinned(model=...)`) are unchanged; `model` is now a route key (identical to the model name in legacy mode). The shims `Classifier.classify` and `Extractor.extract` pass `model=self._route.primary.key` (not `settings.primary_model`), so they work in named mode; a named-mode test calls each shim with a backend name that differs from `primary_model`. Each call becomes `self._registry.invoke(target.backend, LLMRequest(prompt=user, system=system), JsonObject, timeout=DOC_REQUEST_TIMEOUT_SECONDS, model=target.model).root`.

Doc error mapping (replaces the `requests` handling; message prefixes kept):

| `BackendError.reason` | Classifier | Extractor |
|---|---|---|
| `timeout` | re-raise the `BackendError` unwrapped (replaces the unwrapped `requests.exceptions.Timeout`; the pipeline treats it as non-transient and triages without retry) | same |
| `exit` | `ClassifierError(f"HTTP error calling {exc.backend}: {exc.detail}", transient=True)` | `IncompleteExtraction([f"HTTP error: {exc.detail}"], transient=True)` |
| `parse` | `ClassifierError(f"Could not parse classifier JSON response: {exc.detail}", transient=False)` | `IncompleteExtraction([f"could not parse model response as JSON: {exc.detail}"])` |
| `schema` (reply is valid JSON but not an object) | `ClassifierError("classifier response is not a JSON object", transient=False)` | `IncompleteExtraction(["could not parse model response as JSON: not an object"])` |

The full-classify path now rejects a non-object reply as `schema`; before, it would have crashed with `AttributeError` on `.get`. Field-level checks (`missing field`, coercion, partial results, pinned merges, summary normalization) stay in doc and run on `JsonObject.root` exactly as today.

### Pipeline and composition root

```python
@dataclass(frozen=True)  # existing PipelineServices
class PipelineServices:
    ...  # existing fields
    llm_route: DocLLMRoute | None = None   # None -> resolve_doc_route(settings.classifier, {})
```

- `Pipeline.__init__` stores `self._route = services.llm_route or resolve_doc_route(settings.classifier, {})`.
- The three `_retry_llm_call` sites pass `primary_model=self._route.primary.key`, `fallback_model=self._route.fallback.key` (values unchanged in legacy mode).
- `extraction_method = f"llm:{self._route.primary.key}"` (unchanged in legacy mode: `llm:qwen3:30b-a3b`).
- `retry_llm_call` signature unchanged.

`src/tools/bim/dependencies.py`:

```python
def get_classifier(settings: DocSettings, llm: Mapping[str, ...] | None = None) -> Classifier
def get_extractor(settings: DocSettings, llm: Mapping[str, ...] | None = None) -> Extractor
def get_health_checker() -> Callable[..., None]          # returns check_health
def get_pipeline(settings: DocSettings, repo: ZettelRepository, llm: Mapping[str, ...] | None = None) -> Pipeline
    # route = resolve_doc_route(settings.classifier, llm or {}); registry = build_registry(route.backends)
    # Classifier(settings.classifier, route=route, registry=registry); Extractor(..., route=route, registry=registry)
    # PipelineServices(..., llm_route=route)
```

`src/tools/bim/commands/doc/shared/health.py`:

```python
def check_health(settings: DocSettings, llm: Mapping[str, ...] | None = None) -> None
```

After the tesseract/ocrmypdf binary checks, for each distinct backend name in `(route.primary, route.fallback)`:

- `ollama`: today's `_check_ollama(endpoint, model)` with model = the target's model, else the entry's model; skip the pulled-model check when both are `None`. Messages unchanged.
- `llamacpp`, `openai`: today's `_check_llamacpp(endpoint)` (`GET /v1/models`); the message names the kind (`llama.cpp server` for `llamacpp`, `OpenAI-compatible server` for `openai`).
- `claude`: `shutil.which("claude")` else `MissingDependency("claude not found on PATH")`.
- `command`: `shutil.which(argv[0])` else `MissingDependency(f"{argv[0]} not found on PATH")`.

Legacy mode with defaults checks only the primary (same backend twice is checked once), so today's health behavior is unchanged.

`src/tools/bim/doc_cli.py`: every `get_health_checker()(settings.doc)` becomes `get_health_checker()(settings.doc, settings.llm)`; `get_pipeline(settings.doc, get_repo())` becomes `get_pipeline(settings.doc, get_repo(), settings.llm)`.

## Data flow

```
buvis-bim.yaml --> BimSettings.llm (validated union per entry)
                   BimSettings.doc.classifier --resolve_doc_route--> DocLLMRoute (validator fails load on bad names)
doc_cli --> dependencies.get_pipeline(doc, repo, llm)
            --> route, build_registry(route.backends) --> Classifier/Extractor(registry, route)
Pipeline._classify --retry_llm_call(primary.key, fallback.key)--> Classifier.classify_with_model(model=key)
   --> route.target(key) --> registry.invoke(target.backend, LLMRequest(system, user), JsonObject, timeout=60, model=target.model)
       --> HttpBackend / ClaudeBackend / CommandBackend .complete
           --> transport --> reply text --> parse_json_text --> validate_payload(schema) --> JsonObject
   <-- BackendError(reason) --> doc mapping (ClassifierError / IncompleteExtraction / unwrapped timeout)
   --> existing field coercion, pinned merge, triage decision (unchanged)

future tx (00153): registry.invoke(tx.backend, request, IngestPayload, timeout=source_timeout_seconds, unattended=<scheduled>)
```

Providers receive only the request text (system + prompt) and, for Claude, the JSON schema. No adapter receives a vault path, the CLI subprocesses run in an empty temp directory, and the Claude adapter runs with no built-in tools, no MCP servers, no plugins, hooks or skills (the isolation flags in `## Interfaces & contracts` / `claude.py`).

## Reuse inventory

- `src/tools/bim/commands/doc/shared/llm.py:chat_request` / `chat_content` - the Ollama and llama.cpp wire shapes. Moved (not copied) into `shared/llm/http.py` as `build_chat_request` / `read_chat_content`, generalized by `kind` and a caller schema; the llama.cpp grammar and `enable_thinking: False` notes move with them.
- `src/tools/klyreon/backends/claude.py:ClaudeBackend` - argv, temp cwd, stdin prompt, timeout cushion, envelope parsing and the error mapping. Ported to `shared/llm/claude.py` with the schema supplied by the caller instead of the hard-coded `IngestPayload`.
- `src/tools/klyreon/backends/base.py:BackendReason` / `BackendError` - the closed reasons. Ported to `shared/llm/base.py`, with a `backend` name added so a message says which configured entry failed.
- `src/tools/klyreon/backends/__init__.py:get_backend` - name-to-adapter dispatch with lazy adapter imports. Ported as `build_backend`.
- `src/tools/klyreon/backends/stub.py:StubBackend` - not ported as shipped code (the PRD makes the stub test-only); tests implement the `Backend` protocol directly in `test_llm_registry.py`. 00153 can add a stub under `tests/` when ingest needs one.
- `src/tools/bim/commands/doc/shared/health.py:_check_ollama` / `_check_llamacpp` - reused as is, called per resolved backend.
- `src/tools/bim/commands/doc/shared/pipeline_helpers.py:retry_llm_call` - reused unchanged; only the strings it receives come from the route.
- HTTP client: `requests` (already an optional dependency via `[doc]`, and transitively via `jira` in `[bim]`). Tests keep the existing `sys.modules["requests"]` fake, so most transport mocks in the doc suites stay as they are.
- Synonym greps for anything else doing this: `rg -n "subprocess.run\(" src/tools/bim` (only health probes, git, OCR), `rg -n "json_schema|model_json_schema" src/tools/bim` (none outside doc llm.py), `rg -n "urllib.request" src/tools/bim` (`shared/suggest_tags.py` only, a tag-suggestion HTTP call that is not a chat backend). `~/.claude/rules-library/rationalizations.md` synonym sets were not consulted; verbs tried: invoke/call/complete/run/post/chat, nouns: backend/llm/model/schema/endpoint.

## Alternatives considered

1. **Smallest diff: keep doc's transport, add the registry only for tx.** Add `shared/llm/` with Claude and command adapters and leave doc on `requests` + `chat_request`. Smallest change, zero doc risk. Rejected: it violates M18/M21 (one layer, doc moves over) and keeps two HTTP stacks.
2. **Doc calls the registry with strict pydantic schemas for classifier and extractor output.** Cleaner contract, but a strict schema turns "missing field" and coercion problems into a single `schema` error and loses partial extraction results and the per-field triage reasons. It would rewrite doc domain rules, which the PRD forbids. Rejected.
3. **Chosen: shared registry with caller-owned schemas; doc passes the permissive `JsonObject` and keeps its own field logic; legacy config resolves to a synthetic HTTP entry; route keys keep the retry helper string-based.** Larger than option 1 by the doc rewire (classifier, extractor, health, pipeline, composition root, CLI call sites). The extra size buys one transport and one error taxonomy for both callers, named backends for doc (including Claude or a command backend as classifier), and no change for existing configs.

Also weighed: stdlib `urllib` instead of `requests` for the HTTP adapter. It avoids an optional dependency for tx-only users, but it would force rewriting every doc transport mock and loses `raise_for_status`. `requests` is already installed by both `[doc]` and `[bim]`, so it stays; a missing `requests` is a clear `exit` error.

## Risks & edge cases

- **Timeout assertion change.** Doc unit tests that expect `requests.exceptions.Timeout` to escape now expect `BackendError` with `reason == BackendReason.TIMEOUT`. The pipeline-level behavior (no retry, straight to triage) is unchanged and its tests (`TestPipelineTimeoutShortCircuit`) keep passing because the pipeline catches `Exception`. The triage reason text changes from `classifier error: <requests message>` to `classifier error: [timeout] ollama: no reply from ...`.
- **Retry semantics in named mode.** With no `fallback`, the fallback attempt hits the same named backend and model again (one more try), instead of switching models. This is the honest equivalent of "fallback" when the user did not name one.
- **`extraction_method` in named mode** is `llm:<backend name>`, not a model id. It is stored in the state DB; legacy configs keep `llm:<model>`.
- **Config validator scope.** `BimSettings` now fails to load when `doc.classifier.backend` names nothing. A config with a typo used to fail at pydantic too (it was a `Literal`), so this is not a new failure class.
- **Claude envelope drift.** Newer Claude CLIs put `--json-schema` output in `structured_output`; older ones in `result`. Both are read. The adapter is the one place to re-verify when the CLI changes. Live Claude qualification is in 00153.
- **Generic command trust.** A command backend is refused for unattended runs unless `unattended: true`. Nothing can verify that the command has no tools; docs say so.
- **Env-var config.** `BUVIS_BIM_LLM__<NAME>__KIND=...` works through the nested delimiter, but a discriminated union from env vars is fiddly; docs show YAML only.
- **Next changes and what this boxes in:**
  1. 00153 ingest calls `registry.invoke(tx.backend, ..., IngestPayload, unattended=...)` and adds the `tx.backend` existence check; nothing here blocks that. The default `tx.backend = "claude"` needs an `llm.claude` entry (or 00153 adds a built-in default); this PRD adds no implicit entries.
  2. 00154 schedule passes `unattended=True`; the refusal is already in `LLMRegistry.get`.
  3. More agent CLI adapters (codex, kiro): add a `kind` to the union, a module and a `build_backend` branch. API keys for remote OpenAI-compatible servers (`api_key_env`) are not modeled yet; adding a field later is additive.

## Test strategy outline

- `tests/tools/bim/test_llm_registry.py` (no network, no CLIs): per-name selection with two fake `Backend` implementations; unknown name -> `LLMConfigError`; unattended refusal for an unsafe backend and acceptance with `unattended=True` on a safe one; `require_strict_schema` rejects a model without `extra="forbid"`, rejects a forbid parent with a default-extra child (inside a list and inside a union), accepts a `dict[str, str]` field and `JsonObject`; independent doc (`JsonObject`) and tx-like (strict model) schemas validate through one registry; an extra key in a strict-schema reply -> `schema`; `LLMBackendSettings` rejects unknown `kind`, cross-kind keys, empty `argv`; `build_registry` builds the right adapter type per kind; no config value builds a stub.
- `tests/tools/bim/test_llm_backends.py`:
  - `-k http`: fake `requests` in `sys.modules`; request URL and body for each kind (ollama `format: json`; llamacpp `json_schema` + `enable_thinking: False`; openai without `chat_template_kwargs`); timeout passed through; Timeout -> `timeout`; connection error / 500 / bad envelope JSON -> `exit`; missing `choices` -> `parse`; non-JSON content -> `parse`; schema mismatch -> `schema`; scratch vault path never appears in URL or body; missing model for ollama -> `LLMConfigError`.
  - `-k http` also: `content: null` (openai) and an object `content` (ollama) -> `parse`, never a raw `TypeError`; a body over `MAX_REPLY_BYTES` -> `exit`; a 302 -> `exit` and `allow_redirects=False` asserted; a fake `post` that blocks on an event -> the caller gets `timeout` within the deadline (small timeout, then the test releases the event).
  - `run_cli` (in `-k command`, real subprocesses using `sys.executable -c ...` scripts, no network): a script that spawns a sleeping child and then sleeps -> `timeout`, and the child pid is gone afterwards (process group killed); a script that writes stdout forever -> `exit` (overflow) before the timeout; a script that writes stderr forever and then exits 1 -> `exit` with a bounded excerpt; invalid UTF-8 on stdout -> `parse`; non-UTF-8 stderr does not raise.
  - `-k claude`: patch `shutil.which` and the `run_cli` seam; argv exactly as specified, including every isolation flag (with and without model); stdin is `request.as_text()`; run_cli timeout = timeout + 30; missing executable, timeout, non-zero exit -> `exit`/`timeout`; `is_error` envelope -> `exit`; `structured_output` and `result` (string and object) both accepted; invalid JSON -> `parse`; mismatch -> `schema`.
  - `-k command`: argv passed as a list with `shell` unset; prompt only on stdin, never in argv; stdout JSON validated; timeout, missing executable, non-zero exit, bad JSON, schema mismatch; `unattended_safe` follows `unattended`.
  - "Happy path" parametrized: one identical fake reply through each backend validates against the same caller schema.
- Doc suites: `test_llm.py` rewritten for `build_chat_request`/`read_chat_content` (same assertions as today's `chat_request`/`chat_content` tests) and `resolve_doc_route` (legacy defaults: endpoint `http://localhost:11434`, models `qwen3:30b-a3b`/`qwen3:14b`; named primary/fallback; named entry wins over the legacy word; unknown names; fallback in legacy mode rejected). `test_settings_models.py`: defaults unchanged (`triage_threshold 0.85`, `max_retries 2`), `backend` accepts a name, `fallback` field. `test_dependencies.py`: an old config without `llm` resolves to the original endpoint and models; a named config builds one shared registry. `test_health.py`: existing assertions plus claude/command/openai checks. `test_classifier.py`, `test_extractor.py`, `*_pinned.py`: keep every behavioral assertion; only the timeout tests change their expected type. Retry, fallback, triage and partial extraction stay covered by the existing pipeline tests.
- `tests/tools/bim/test_settings.py`: `llm` map loads; bad `doc.classifier.backend` fails load.
- Closeout: full `uv run pytest` and `uv run mypy src/lib/ src/tools/`.

## Review log

Dispatch 1 fixed blockers: (B1) Claude adapter left MCP servers, plugins, hooks and skills reachable behind `--tools ""` -> isolation flags added and pinned, headless probe made part of the task; (B2) `parse_json_text` leaked `TypeError` on a null/non-string reply -> mapped to `parse`, `read_chat_content` returns `str` or raises.

Dispatch 1 non-blockers (recorded, not fixed):
- NB1 `Classifier.classify()` / `Extractor.extract()` shims pass `settings.primary_model`; in named mode that is not a route key. Shims should pass the route's primary key.
- NB2 A named ollama/openai entry without `model` loads and passes health, then fails every doc call; `resolve_doc_route` could reject it at load.
- NB3 Doc `exit` message reads "HTTP error calling claude: ..." for CLI backends and doubles the HTTP prefix; consider `str(exc)`.
- NB4 Ollama always sends `format: "json"`; for strict (tx) schemas it could send the JSON schema in `format`.
- NB5 CLI timeouts kill only the direct child, not its process group.
- NB6 Named-mode `extraction_method` (`llm:<backend>`) loses model provenance.
- NB7 Files outside the PRD list (`doc_cli.py`, `test_health.py`, `tests/tools/bim/test_settings.py`) must be in the plan's allowlist; the `backend="vllm"` rejection test moves to a BimSettings load test.

Dispatch 1 questions:
- Q1 How do Classifier, Extractor and Pipeline share one route and one registry? (Suggested: take `route` + `registry`; `get_pipeline` passes the same objects to all three.)
- Q2 Is `--help` enough for "verify installed CLI flags headlessly"? (Partly answered by the headless probe step added for B1.)

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 7, question 2

Dispatch 2 note: the first codex run could not read files (`sandbox-exec: sandbox_apply: Operation not permitted` inside the nested sandbox) and returned only an environment blocker; it was re-run once with the design doc and the main changed sources inlined. The counts below are from that re-run.

Dispatch 2 fixed: (CS1) unbounded adapter resources -> HTTP total deadline and `MAX_REPLY_BYTES` cap via streamed read; `run_cli` with process-group kill on timeout and after exit, temp-file output, stdout cap, strict UTF-8 -> `parse` (also closes NB5 and the decoding non-blocker below); (B3) nested models escaped the strict-schema check -> `require_strict_schema` walks the whole JSON schema; (B4) named-mode shims -> `classify()`/`extract()` pass `route.primary.key` (closes NB1), and Classifier/Extractor take the shared `route`/`registry` (answers Q1).

Dispatch 2 non-blockers (recorded, not fixed):
- NB8 Subprocess output decoding could escape the closed categories (closed by the CS1 `run_cli` fix).
- NB9 Claude envelope detection is ambiguous for a bare caller payload that has `result`, `structured_output` or `is_error` keys; the headless probe should settle the envelope shape, after which bare-payload support could be dropped.
- NB10 Named ollama/openai entry without `model` (same as NB2).
- NB11 `extraction_method` names the primary even when the fallback produced the result (pre-existing in legacy mode too).

Dispatch 2 questions:
- Q3 Compatibility claims rest on sources not inlined for codex (tests, pipeline, dependencies, doc_cli); dispatch 1 read those directly and checked them.

dispatch 2 (codex): cardinal-sin 1, blocker 2, non-blocker 4, question 1

Dispatch 3 (codex verification, design and sources inlined) confirmed B1-B4 fixed and found CS1 incomplete:
- CS2 subprocess stdout/stderr went to temp files with the size check only after exit (disk not bounded).
- CS3 `requests` follows redirects and reads redirect bodies outside the cap.
- B5 the HTTP deadline was checked only between chunks, so a trickling server could block one read past it.

These were edited into the doc after dispatch 3 (pipe readers with in-memory caps and process-group kill on overflow; `allow_redirects=False` with 3xx -> `exit`; HTTP call in a worker with `future.result(timeout=...)` so the caller is released at the deadline, residual blocked worker thread accepted and documented). No dispatch remains to verify them, so they count as open for this run.

dispatch 3 (codex): cardinal-sin 2, blocker 1, non-blocker 0, question 0
