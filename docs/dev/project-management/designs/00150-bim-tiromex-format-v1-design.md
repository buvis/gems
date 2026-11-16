# Design: bim tiromex format and foundation commands (PRD 00150)

PRD: `docs/dev/project-management/prds/wip/00150-bim-tiromex-format-v1.md`.
Requirements authority: `docs/dev/project-management/intake/processed/00149-merge-klyreon-into-bim/discovery.md`.

## Architecture fit

- A new command group `bim tx` beside `bim doc`: command classes under
  `src/tools/bim/commands/tx/`, cross-command code under
  `src/tools/bim/commands/tx/shared/`, Click wiring in `src/tools/bim/tx_cli.py`
  (same split as `doc_cli.py`; the `no-framework-in-commands` pre-commit hook
  forbids `import click` and `from buvis.pybase.adapters import` anywhere under
  `src/tools/*/commands/`).
- One additive edit lands in `src/lib/`: a `stderr` keyword on the console
  adapter's `warning` and `failure` (see CLI). The shared code imports the zettel library
  (`ZettelData`, `MarkdownZettelFileParser`, `CreateZettelUseCase`) and no UI
  framework. `src/tools/klyreon/` is read-only port input and is never imported.
- One persisted representation: a tiromex note is a bim note. The tx layer keeps
  a read view (`TxNote`) around `ZettelData`; it adds no second model on disk.
- Commands return `CommandResult`; `tx_cli.py` renders. Serve and TUI adapters
  come in PRD 00154 and will call these same classes.

## Module placement

New files:

| Path | Holds |
|------|-------|
| `src/tools/bim/tx_cli.py` | Click group `tx` and the four handlers, `register_tx_group` |
| `src/tools/bim/commands/tx/__init__.py` | empty `__all__` |
| `src/tools/bim/commands/tx/new.py` | `CommandTxNew` |
| `src/tools/bim/commands/tx/validate.py` | `CommandTxValidate` |
| `src/tools/bim/commands/tx/export_claims.py` | `CommandTxExportClaims` |
| `src/tools/bim/commands/tx/status.py` | `CommandTxStatus`, `staleness_line` |
| `src/tools/bim/commands/tx/shared/__init__.py` | empty `__all__` |
| `src/tools/bim/commands/tx/shared/settings.py` | `TxSettings` |
| `src/tools/bim/commands/tx/shared/paths.py` | `TiromexPaths`, confinement, note listing, state dir |
| `src/tools/bim/commands/tx/shared/format.py` | vocabularies, `TxNote`, parse, classify, links, serialize |
| `src/tools/bim/commands/tx/shared/validator.py` | `Diagnostic`, `validate_note`, `validate_tiromex` |
| `src/tools/bim/commands/tx/shared/claims.py` | `collect_claims` |
| `tests/tools/bim/tx/__init__.py`, `conftest.py`, `test_settings.py`, `test_scope.py`, `test_format.py`, `test_commands.py` | tests |
| `docs/reference/bim/tiromex/zettel-format-specification.md` | revised format spec |

Edited files: `src/tools/bim/cli.py` (register the group),
`src/tools/bim/settings.py` (two fields), `src/tools/bim/dependencies.py`
(`get_tiromex_paths`), `src/tools/bim/manifest.toml`, `src/tools/bim/SKILL.md`,
`docs/source/tools/bim.rst`, `CHANGELOG.md`, `tests/tools/bim/test_format_note.py`,
`AGENTS.md` (one sentence, see CLI),
`src/lib/buvis/pybase/adapters/console/console.py` (`stderr` keyword on
`warning` and `failure`), `tests/lib/pybase/adapters/test_console_adapter.py`.

## Interfaces & contracts

### Settings

`src/tools/bim/commands/tx/shared/settings.py`:

```python
class TxSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: str = "claude"
    max_sources_per_run: int = 5
    source_timeout_seconds: int = 900
    max_zettel_body_lines: int = 60
    maintenance_window_days: int = 7
    pruning_enabled: bool = False
    prune_window_days: int = 365
    git_identity_name: str = "bim-tx"
    git_identity_email: str = "bim-tx@localhost"
```

`BimSettings` (`src/tools/bim/settings.py`) gains exactly:

```python
    tiromex_folder: str = "tiromex"
    tx: TxSettings = Field(default_factory=TxSettings)
```

Env overrides follow the existing prefix and delimiter:
`BUVIS_BIM_TIROMEX_FOLDER`, `BUVIS_BIM_TX__MAX_SOURCES_PER_RUN`, and so on. An
unknown key under `tx:` is rejected by `extra="forbid"`. `path_articles` stays
(PRD 00152 retires it). The source setting `model` is not ported: no command in
this PRD calls a backend, and PRD 00151 owns backend settings.

### Paths and scope

`src/tools/bim/commands/tx/shared/paths.py`:

```python
@dataclass(frozen=True, slots=True)
class TiromexPaths:
    vault_root: Path      # path_zettelkasten.expanduser().resolve().parent (as CommandCreateNote)
    zettelkasten: Path    # path_zettelkasten.expanduser().resolve()
    folder: Path          # resolved zettelkasten / tiromex_folder

def resolve_tiromex(path_zettelkasten: Path, folder_name: str) -> TiromexPaths: ...
def confine(paths: TiromexPaths, vault_rel: str) -> Path: ...
def to_vault_rel(paths: TiromexPaths, file: Path) -> str: ...
def iter_note_files(paths: TiromexPaths) -> list[Path]: ...
def tx_state_dir() -> Path: ...
def read_last_maintain() -> str | None: ...
```

- `resolve_tiromex` raises `ValueError` when `folder_name` is empty, is
  absolute, has more than one path part, or is `.` or `..`; when
  `path_zettelkasten` is not a directory; when `zettelkasten / folder_name`
  is a symlink (`Path.is_symlink()`); or when its resolved path is not exactly
  `zettelkasten / folder_name`. A tiromex folder that is a link to the
  zettelkasten itself, to a sibling folder or to any other place is refused,
  so tx can never be pointed at private notes. It does not create the folder.
- `confine` takes a vault-relative POSIX path (`notes/tiromex/<id>.md`). It
  raises `ValueError` when the path is absolute, has a `..` part, or resolves
  (symlinks followed) outside `paths.folder`. It returns the resolved path and
  does not require the file to exist.
- `to_vault_rel` returns the POSIX path of `file` relative to `vault_root`.
- `iter_note_files` returns the sorted `*.md` files under `paths.folder`
  (recursive), leaving out any whose resolved path is outside `paths.folder`.
  A missing folder gives `[]`.
- `tx_state_dir` is `$XDG_STATE_HOME/bim/tx`, else `~/.local/state/bim/tx`.
  `read_last_maintain` reads the `last_maintain` string from
  `tx_state_dir() / "state.json"` and returns `None` when the file is absent,
  unreadable, not a JSON object, or has no string under that key (so a
  non-string value reads as "never run"). Nothing in
  this PRD writes state. No custom exception classes: every failure is a
  `ValueError`.

`src/tools/bim/dependencies.py` gains:

```python
def get_tiromex_paths(settings: BimSettings) -> TiromexPaths:
    """resolve_tiromex(Path(settings.path_zettelkasten).expanduser(), settings.tiromex_folder)"""
```

### Format

`src/tools/bim/commands/tx/shared/format.py`.

Vocabularies (string enums, values unchanged from the source):

- `ConceptType`: `thesis`, `argument`, `aporia`, `question`, `example`, `observation`
- `Assent`: `accepted`, `tentative`, `rejected`, `unknown`
- `Lifecycle`: `fleeting`, `literature`, `evergreen`
- `DoubtMode`: `disagreement`, `regress`, `context-relative`, `assumption`, `circular`
- `Relation`: `supports`, `contradicts`, `exemplifies`, `supersedes`, `defines`,
  `analogous-to`, `causes`, `requires`, `broader-than`, `narrower-than`
- `TRANSITIVE_RELATIONS = ("requires", "broader-than", "narrower-than")` (a tuple, in `Relation` order, so diagnostics come out in a stable order)
- `CLAIM_BEARING_CONCEPT_TYPES = frozenset({"thesis", "argument", "observation"})`
- `CONCEPT_NOTE_TYPES = ("note", "definition", "procedure", "wiki-article", "cheatsheet", "snippet", "course", "ai-prompt")`
- `INDEX_TYPE = "index"`, `TX_RUN_TYPE = "tx-run"`
- `FORBIDDEN_TAGS = frozenset({"person", "book"})`
- `MEMBERS_OPEN = "<!-- tx:members -->"`, `MEMBERS_CLOSE = "<!-- /tx:members -->"`
- `MIRROR_PREFIX = "mirror:"`

```python
class NoteKind(str, Enum):
    CONCEPT = "concept"
    INDEX = "index"
    RUN = "run"
    PLAIN = "plain"

@dataclass(frozen=True, slots=True)
class WikiLink:
    target: str   # vault-relative, no ".md": "notes/tiromex/20260411145300"
    title: str    # "" when the link has no "|title" part (readable, but a link-shape error)

@dataclass(slots=True)
class TxNote:
    path: str         # vault-relative POSIX path, with ".md"
    data: ZettelData  # raw parse: metadata, reference (backmatter), sections
    kind: NoteKind
    body: str         # raw body text, see parse_note

def parse_note(text: str, path: str) -> TxNote: ...
def read_note(paths: TiromexPaths, file: Path) -> TxNote: ...
def classify(data: ZettelData) -> NoteKind: ...
def parse_links(value: object) -> list[WikiLink]: ...
def format_links(links: list[WikiLink]) -> str: ...
def relations(data: ZettelData) -> list[tuple[str, WikiLink]]: ...
def parents(data: ZettelData) -> list[WikiLink]: ...
def sources(data: ZettelData) -> list[str]: ...
def link_file(target: str) -> str: ...
def h1_titles(body: str) -> list[str]: ...
def body_lines(body: str) -> list[str]: ...
def as_datetime(value: object) -> datetime | None: ...
def serialize(data: ZettelData) -> str: ...
```

- `TxNote.body` is the raw body: the text after the front matter block
  (the first match of `\A---\n.*?\n---\n`, dot matches newline) up to, not
  including, the first line that is exactly `---` (the backmatter
  separator), or to the end of the text. Every body rule reads this string.
  No rule reads `data.sections`: bim's section splitter is lossy (its heading
  regex is not anchored to the line start, so `I write C# and F#` becomes a
  heading; text before the first heading is dropped; an H1 with no trailing
  newline is not a heading at all; probes 2026-11-16).
- `h1_titles` returns the text of every line of `body` that matches
  `^#[ \t]+(\S.*)$` (multiline), stripped. This is the source `_check_h1`
  predicate on the same input the source used.
- `body_lines` returns the non-blank lines of `body` (H1 included).
- `as_datetime` is the one date reader: a `datetime` is returned as is; a
  `datetime.date` becomes midnight of that day; a string goes through
  `datetime.fromisoformat` (failure gives `None`); any other value gives
  `None`. A naive result gets the local timezone
  (`.astimezone()`), so every comparison is between aware values.

- `parse_note` runs `MarkdownZettelFileParser.parse(text)` (raw: no fixers, no
  migration) and classifies. A text that does not start with a `---` front
  matter block, or whose YAML fails, raises `ValueError`.
- `classify`: `CONCEPT` when the metadata has the key `concept-type` (any
  value); else `INDEX` when `type == "index"`; else `RUN` when
  `type == "tx-run"`; else `PLAIN`.
- Backmatter form. One line per key. A relation with several targets joins the
  wikilinks with `", "` on that one line:
  `- supports:: [[notes/tiromex/1|A]], [[notes/tiromex/2|B]]`. tx never writes a
  repeated key, because `bim format` rewrites a repeated backmatter key into a
  Python list literal today (probe 2026-11-16). `parse_links` accepts a string
  or a list of strings (a hand-written repeated key parses to a list) and finds
  links with the regex `\[\[([^\]|]+)(?:\|([^\]]*))?\]\]`; it never splits on
  commas, so a title may hold one. `format_links` is its inverse for writing;
  it removes the characters `"`, `\`, `[`, `]` and `|` from each title,
  because bim's backmatter reader quotes a bracketed value without escaping
  and a `"` in a title makes the note unparseable (probe 2026-11-16).
- `relations` reads the ten `Relation` keys of `data.reference`, in enum order,
  one tuple per link. `parents` reads the `parent` key. `link_file(target)`
  returns `target + ".md"`. A target that ends with `.md` or holds `#` is a
  `link-shape` error, not normalised.
- `sources` reads the `source` key: a string or list of strings, each split
  before every later `mirror:` (regex `,\s*(?=mirror:)`), stripped. Values are
  returned as written; resolving them is PRD 00152.
- `serialize` returns `MarkdownZettelFormatter.format(data)`, the same
  formatter `bim format` uses. `bim format` reads through the repository
  (Rust parser plus fixers), so its output can differ from `serialize` of a
  raw parse by the default keys the fixers add.
- Membership tests use frozensets of the enum values
  (`CONCEPT_TYPE_VALUES`, `ASSENT_VALUES`, `LIFECYCLE_VALUES`,
  `DOUBT_MODE_VALUES`, `RELATION_VALUES`), never `x in EnumClass` (a
  `TypeError` for a non-member on Python 3.11). A value that is not a string
  fails the enum rule that reads it. `title` and each tag are compared as
  `str(value)` (YAML gives `title: 2026` as an int). `id` is compared as
  `str(id)`.
- Frontmatter order on write is bim's: `id`, `title`, `date`, `tags`, `type`,
  `publish`, `processed`, then every other key in insertion order. Unknown keys
  survive because the formatter writes all metadata.

Doubt targets are frontmatter data, not links:
`doubts[].target.to` is a vault-relative path with `.md`
(`notes/tiromex/20260301101500.md`), `doubts[].target.claim` a claim id.

Index notes: `type: index`, a 14-digit `id` and the file name `<id>.md` like
every tx note, title starts with `§ `, and at most one members
block `<!-- tx:members -->` ... `<!-- /tx:members -->` in the body. A member
note links to its index with `- parent:: [[notes/tiromex/<stem>|§ Title]]`.

### Validation

`src/tools/bim/commands/tx/shared/validator.py`:

```python
@dataclass(frozen=True, slots=True)
class Diagnostic:
    path: str            # vault-relative
    rule: str
    message: str
    line: int | None = None

def validate_note(note: TxNote, *, max_body_lines: int = 60) -> list[Diagnostic]: ...
def validate_tiromex(paths: TiromexPaths, *, max_body_lines: int = 60) -> list[Diagnostic]: ...
```

`validate_tiromex` reads every file from `iter_note_files`; a read or parse
failure gives one `parse-error` and that file is left out of the graph. Rule
ids are kept from the source validator wherever the rule survives.

`validate_note` runs every rule that needs one note only. The graph rules need
`TiromexPaths` and run only in `validate_tiromex`: `parse-error`,
`path-confinement`, `dangling-link`, `dangling-moc`, `dangling-doubt-target`,
`transitive-cycle`. `validate_tiromex` returns the per-note diagnostics of
each file, in path order, then the graph diagnostics.

`transitive-cycle`: adjacency keys are `TxNote.path` of the parsed concept
notes; an edge is `to_vault_rel(paths, confine(paths, link_file(link.target)))`
(the resolved file, so `./` parts and symlinks inside the folder name the same
node; a target that fails `confine` gives no edge) and is kept only when it is
such a key. Note files come from `iter_note_files`, whose paths are already
resolved, so keys and edges are in the same form. The source `_first_cycle` DFS ports over that map. Relations are walked
in `TRANSITIVE_RELATIONS` order.

| Rule id | Kinds | Fails when |
|---------|-------|------------|
| `parse-error` | all | file unreadable or not parseable |
| `required-field` | all | `id`, `title`, `date` or `type` missing or blank |
| `publish-true` | concept, index, run | `publish` is `true` |
| `legacy-colon-tag` | concept, index, run | a tag contains `:` |
| `forbidden-tag` | concept, index, run | a tag is `person` or `book` |
| `h1-exactly-one` | concept, index, run | `len(h1_titles(note.body)) != 1` |
| `h1-title-mismatch` | concept, index, run | there is one H1 and its text differs from `str(title)` |
| `empty-body` | concept, index | `body_lines(note.body)` holds no line other than the H1 |
| `zettel-id-format` | concept, index, run | `str(id)` is not exactly 14 digits |
| `id-filename-mismatch` | concept, index, run | `str(id)` differs from the file stem |
| `id-created-mismatch` | concept, index, run | `zettel-id-format` did not fire, `d = as_datetime(date)` is not `None`, and `str(id)` equals neither `d.strftime("%Y%m%d%H%M%S")` (the value's own offset) nor `d.astimezone().strftime(...)` (the local zone; `bim format` rewrites dates into it) |
| `type-species` | concept | `type` is not in `CONCEPT_NOTE_TYPES` |
| `concept-type-enum` | concept | value not in `ConceptType` |
| `assent-enum` | concept | present and not in `Assent` |
| `lifecycle-enum` | concept | present and not in `Lifecycle` |
| `claims-shape` | concept | `claims` present and not a list |
| `claim-shape` | concept | a claim is not a mapping with `id` and `statement` |
| `claims-required` | concept | concept-type in `CLAIM_BEARING_CONCEPT_TYPES` and `claims` is missing, `None` or an empty list |
| `aporia-no-claims` | concept | concept-type `aporia` and `claims` is a non-empty list |
| `claims-count` | concept | `claims` is a list with more than 3 entries; or an empty list on a concept type that is neither claim-bearing nor `aporia` (1 to 3 when present) |
| `doubts-shape` | concept | `doubts` present and not a list |
| `doubt-shape` | concept | a doubt is not a mapping with `mode`, `claim`, `rationale` |
| `doubt-mode-enum` | concept | a doubt mode not in `DoubtMode` |
| `doubt-target-shape` | concept | on a `disagreement` doubt that has the key `target` (as in the source, a doubt with no target is valid), `target` is not a mapping, or lacks `to`, or lacks `claim` |
| `link-shape` | concept, index | a relation or `parent` value holds no wikilink, or a link has a blank title (`[[t]]`, `[[t|]]`, `[[t| ]]`), or a link target ends with `.md` or holds `#` |
| `source-shape` | concept | a `source` value does not start with `mirror:`, has no `/` after the root name, or its path part is absolute or has a `..` part |
| `path-confinement` | concept, index | a relation, `parent` or doubt target fails `confine` |
| `dangling-link` | concept | a confined relation target is not a regular file (`Path.is_file()`) |
| `dangling-moc` | concept, index | a confined `parent` target is not a regular file |
| `dangling-doubt-target` | concept | a confined doubt `target.to` does not end with `.md` or is not a regular file |
| `orphan-concept` | concept | no `parent` link |
| `oversized-body` | concept, index | `len(body_lines(note.body))` (H1 included, as in the source) exceeds `max_body_lines` |
| `stale-review` | concept, index | `as_datetime(reviewed)` and `as_datetime(updated)` are both not `None` and the first is older |
| `transitive-cycle` | concept | a cycle in one of `TRANSITIVE_RELATIONS`, reported once per relation on the first note of the cycle |
| `index-title` | index | `title` does not start with `§ ` |
| `members-block` | index | the markers in `note.body` are neither none at all nor exactly one open marker followed later by exactly one close marker |

Notes: `PLAIN` notes get only `parse-error` and `required-field`. Run notes
have no `oversized-body` rule. `claims-count` and `forbidden-tag` are new rule
ids (the source enforced neither). `empty-body` is new too: `bim format`
writes a second H1 into a note whose body is only an H1 followed by
backmatter (existing bim defect, probe 2026-11-16: H1 plus `- parent::` gives
two H1 lines; H1 plus one body line plus `- parent::` is stable), so a
concept or index note must hold at least one body line under its H1; `source-shape` replaces the source rule
`dangling-source` until PRD 00152 adds mirror resolution; the source rules
`link-to-source`, `concept-field-on-source`, `aux-kind-enum`, `links-shape`,
`link-rel-enum` have no counterpart (sources left the vault; relations are
backmatter keys). Every `date`, `updated` and `reviewed` value is read through
`as_datetime`; a value it cannot read makes the date rules skip that note (no
crash, no new rule id).

### Claims

`src/tools/bim/commands/tx/shared/claims.py`:

```python
def collect_claims(notes: list[TxNote]) -> list[dict[str, object]]: ...
```

One row per well-formed claim on a `CONCEPT` note, in note-path order then
claim order. Row keys, in this order: `zettel` (vault-relative path), `assent`
(default `"unknown"`), `lifecycle` (default `"fleeting"`), `claim_id`,
`statement`. Rejected notes are included. Other kinds contribute nothing.
Every row value is a string (`str(value)`), so the export never meets a YAML
date or number that `json.dumps` cannot write.

### Commands

All four take a resolved `TiromexPaths`, catch expected errors and return
`CommandResult`. None imports Click or the console.

```python
class CommandTxNew:
    def __init__(self, paths: TiromexPaths, repo: ZettelRepository, *, title: str,
                 zettel_type: str = "note", concept_type: str | None = None) -> None: ...
    def execute(self) -> CommandResult: ...
```

- Creates through `CreateZettelUseCase(paths.zettelkasten, repo)` with a
  private template object (`name = "tx"`, `folder = paths.folder` relative to
  the zettelkasten, no questions, no hooks). bim's factory sets `id` and `date`
  from local time; on a collision the use case waits one second and rebuilds
  (up to five attempts) and reserves the file with `O_EXCL`.
  `FileExistsError`, `ValueError` and `OSError` become a failed
  `CommandResult`.
- Metadata built by the template: `type`, `title`; with `concept_type` also
  `concept-type`, `assent: tentative`, `lifecycle: fleeting`, and for a
  claim-bearing concept type `claims: [{id: c1, statement: <title>}]`. Body is
  the H1 only. bim's fixers add `tags: []`, `publish: false`,
  `processed: false`.
- `zettel_type` must be in `CONCEPT_NOTE_TYPES` minus `wiki-article` (bim's
  migration rewrites `wiki-article` to `note`); `concept_type`, when given, in
  `ConceptType`. A bad value is a failed `CommandResult`, no file.
- Before writing, the command builds the note with `use_case.prepare`, turns
  it into a `TxNote` with `parse_note(serialize(zettel.get_data()), path)`,
  runs `validate_note` on it (graph rules do not apply to a new unlinked
  note; `orphan-concept` and `empty-body` are ignored here: a new note is a
  stub with no parent and no body yet, and it has no backmatter, so the
  duplicate-H1 defect cannot hit it), and refuses with
  `refusing to write an invalid note: [rule] message; ...` when any diagnostic
  remains. `execute` rebuilds the note with a new clock, so this check covers
  the template output (type, concept fields, claims, H1); the id and date
  rules hold by construction in the factory.
- Success: `output` is the absolute path, `metadata = {"id": "<14 digits>", "path": "<vault-relative path>"}`.

```python
class CommandTxValidate:
    def __init__(self, paths: TiromexPaths, *, as_json: bool = False, max_body_lines: int = 60) -> None: ...
```

- JSON output: `json.dumps({"clean": bool, "error_count": int, "errors": [{"path", "rule", "message", "line"}]}, indent=2, sort_keys=True)`,
  `success = not errors`, `metadata = {"error_count": n}`.
- Text output: clean gives `output = "tiromex is clean: <folder>"`; otherwise
  `error = "<n> validation error(s):\n" + lines of "<path>: [<rule>] <message>"`.

```python
class CommandTxExportClaims:
    def __init__(self, paths: TiromexPaths, *, out: Path | None = None, now: datetime | None = None) -> None: ...
```

- Payload keys, in order: `schema_version` (1), `generated` (ISO, local
  offset), `claims` (rows from `collect_claims`); `json.dumps(indent=2)`.
- The command computes `dest = out.expanduser().resolve()` once and uses
  `dest` for the check, for parent creation and for the write (never the raw
  `out`, so `~/x.json` typed inside the vault cannot check one path and write
  another). `dest` is refused when `dest` or any of its parents exists and
  `os.path.samefile(<that path>, paths.vault_root)` is true (the whole vault,
  not only tiromex). Comparing files, not path strings, also catches symlink
  aliases, a different letter case on a case-insensitive volume and macOS
  firmlink paths. Error text starts with
  `--out <out> resolves under the vault root`.
- With `out`: parents of `dest` are created, the file is written with
  `atomic_write_text(dest, text + "\n")`, `output = "wrote <n> claim(s) to <dest>"`.
  Without: `output` is the JSON text. Both set
  `metadata = {"claim_count": n}`; each unparseable note becomes one entry in
  `warnings` (`skipped unparseable note <path>: <reason>`), never a payload
  key.

```python
class CommandTxStatus:
    def __init__(self, paths: TiromexPaths, *, maintenance_window_days: int = 7,
                 prune_window_days: int = 365, pruning_enabled: bool = False,
                 now: datetime | None = None) -> None: ...

def staleness(now: datetime, window_days: int) -> tuple[str, int | None]: ...
def staleness_line(now: datetime, window_days: int) -> tuple[bool, str]: ...
```

- `staleness` returns `(reason, days)`: `("never", None)` when
  `read_last_maintain()` is `None` or an empty string; `("unparseable", None)`
  when `as_datetime` cannot read it; else `("stale", d)` when `d` days is
  more than `window_days`, else `("fresh", d)`. `staleness_line` and the CLI
  warning both derive their wording from it.

- Output lines, in order:
  1. `tiromex: <folder>`
  2. `notes: <total> (concept: <a>, index: <b>, runs: <c>, plain: <d>)`
  3. `lifecycle: <k=v, ...>` or `lifecycle: (none)`
  4. `assent: <k=v, ...>` or `assent: (none)`
  5. `mean links/note: <x>` where `x = round(relation links on concept notes / concept notes, 2)` printed with `str`, and `0.0` when there is no concept note
  6. `aporia notes: <n>  open disagreement doubts: <m>`
  7. `prune candidates: <k> (deletion report-only)` or `(deletion enabled)`
  8. `git: tracked` or `git: NOT a git work tree`
  9. the staleness line
- `metadata` keys: `zettels` (concept notes, the denominator of
  `mean_links`), `notes` (all parsed notes), `lifecycle`,
  `assent`, `mean_links`, `aporia`, `open_disagreements`, `prune_candidates`,
  `pruning_enabled`. No source counts yet (PRD 00153 adds pending sources).
  `lifecycle` and `assent` count concept notes that carry the field. Each
  unparseable file becomes one `warnings` entry, as in the source.
- `staleness_line` returns `(stale, text)` with the source wording:
  `maintenance: never run (stale)`,
  `maintenance: last_maintain unparseable (stale)`,
  `maintenance: last run <d>d ago (stale, window <w>d)`,
  `maintenance: last run <d>d ago (fresh)`.
- Prune-candidate count (interim, private to `status.py`; PRD 00154 moves it to
  `shared/prune.py` and adds the outside-backlink rule): a concept note with
  `lifecycle: fleeting`, assent not `rejected`, empty `delivered-as`, no
  relation links out, no relation link in from another tiromex note, an empty
  corroboration set, and an anchor older than `prune_window_days`. The
  corroboration set of note `n` is
  `(union of sources(s) for every note s with a supports link to n) - set(sources(n))`;
  this drops the source's `include_own=True` on purpose (discovery M26,
  port-plan row 109). The set is computed by a private pure function
  `_corroboration(note: TxNote, notes: list[TxNote]) -> set[str]`, tested on
  its own: while a candidate must have no inbound relation link at all, a
  supporter cannot exist and the clause never decides; PRD 00154 narrows the
  inbound rule and the clause then matters. The anchor is `as_datetime(updated)`, else
  `as_datetime(date)`; with no anchor the note is not a candidate.
- Git line: `git -C <vault_root> rev-parse --is-inside-work-tree` via
  `subprocess.run` with a list argv, captured output, 10 s timeout; any
  failure reads as not a work tree. Private to `status.py` until PRD 00153
  adds `shared/git.py`.

### CLI

`src/tools/bim/tx_cli.py`:

```python
def register_tx_group(cli: click.Group) -> None: ...
```

| Command | Options |
|---------|---------|
| `bim tx new` | `--title` (required), `--type` (`click.Choice`, default `note`), `--concept-type` (`click.Choice`, optional) |
| `bim tx validate` | `--json` |
| `bim tx export-claims` | `--out PATH` (plain `click.Path(path_type=Path)`, no parse-time checks) |
| `bim tx status` | none |

- Command classes and `get_tiromex_paths` are imported inside the handlers.
  A `ValueError` from `get_tiromex_paths` goes to `console.panic`.
- Exit code 1 on a failed result (`ctx.exit(1)` after rendering).
- Machine output (`validate --json`, `export-claims` without `--out`) is
  written with `console.console.out(text, highlight=False)`: Rich's unwrapped,
  unmarked stream. `console.print(text, mode="raw")` wraps at the console
  width and breaks long JSON strings (probe 2026-11-16), so it is not used for
  JSON.
- Rendering, per command (`out` = `console.console.out(text, highlight=False)`;
  `report` = `console.report_result(result, literal=True)`, literal because
  Rich markup would eat the `[rule]` ids, as `muc/cli.py` does):

  | Command | Success output | Warnings | Failure |
  |---------|----------------|----------|---------|
  | `new` | `out` (the path), stdout | none | `report` |
  | `validate` (text) | `report` | none | `report` |
  | `validate --json` | `out` (JSON), stdout; the JSON is printed for a failed result too | stderr | exit 1, nothing more |
  | `export-claims` | `out` (JSON), stdout | stderr | error on stderr |
  | `export-claims --out` | `out` (`wrote <n> claim(s) to <dest>`), stdout | stderr | error on stderr |
  | `status` | `out` (the lines), stdout | stderr | `report` |

  stderr warnings are `console.warning(escape(message), stderr=True)` and
  stderr errors `console.failure(escape(message), stderr=True)`, with
  `rich.markup.escape`, because messages hold note paths and exception text
  that may contain brackets. The `console.panic` message for a
  `get_tiromex_paths` error is escaped the same way. The stdout of the two
  JSON commands holds the payload and nothing else.
- The console adapter gains the stderr path (the one `src/lib/` edit of this
  PRD, additive): in `src/lib/buvis/pybase/adapters/console/console.py`,
  `ConsoleAdapter.warning(self, message: str, *, stderr: bool = False) -> None`
  and
  `ConsoleAdapter.failure(self, message: str, details: str | None = None, *, stderr: bool = False) -> None`.
  With `stderr=True` the same formatted text is printed on
  `rich.console.Console(stderr=True, log_path=False)`, built at call time;
  the default is today's behaviour, byte for byte. tx builds no Rich console
  of its own. `AGENTS.md` (Error Handling, sanctioned exceptions) gains one
  sentence for the `bim tx` JSON payloads written with `console.console.out`.
- Staleness: the `tx` group callback writes one warning
  (`maintenance has never run`, `maintenance state is unreadable`, or
  `maintenance is stale: last run <d>d ago`) through
  `console.warning(..., stderr=True)` (one wording per `staleness` reason
  `never`, `unparseable`, `stale`), when the reason is not `fresh` and
  `ctx.invoked_subcommand != "status"`. `status` carries the line in its own
  output, so every invocation shows it once. No other `bim` command warns.
- `src/tools/bim/cli.py` adds `register_tx_group(cli)` after
  `register_doc_group(cli)`.

### Documentation contracts

- `src/tools/bim/SKILL.md`: the approval rule (lines 17-22) stays word for
  word, followed by one exception paragraph: inside
  `<path_zettelkasten>/<tiromex_folder>/` (default `notes/tiromex/`) an agent
  may read and write without asking. A new
  `## Tiromex` section covers concept fields, the closed vocabularies above,
  claim and doubt rules, the three conflict shapes (aporia, refine,
  supersede), the backmatter relation form and the four `bim tx` commands.
- `src/tools/bim/manifest.toml` `[tool.commands]` gains `tx_new`,
  `tx_validate`, `tx_export_claims`, `tx_status`.
- `docs/reference/bim/tiromex/zettel-format-specification.md` is the source
  spec revised to this design: `date` not `created`, bim key order, backmatter
  relations, index notes, `mirror:` sources, `tx-run`, no source-document
  species. The old file under `docs/reference/klyreon/` stays until PRD 00155.
- `CHANGELOG.md` `[Unreleased]` `### Added`: `- **bim**: ...` one line for
  `bim tx new/validate/export-claims/status` and the tiromex folder.

## Data flow

1. `tx_cli` reads `BimSettings`, calls `get_tiromex_paths`, builds the command.
2. Read commands: `iter_note_files` -> `read_note` (raw parse, classify) ->
   `validate_tiromex` / `collect_claims` / status counters -> `CommandResult`.
3. `new`: template -> `CreateZettelUseCase.prepare` -> `validate_note` ->
   `CreateZettelUseCase.execute` -> `repo.save` (bim formatter, atomic).
4. `export-claims --out`: vault-root refusal -> `atomic_write_text`.
5. `tx_cli` renders: JSON on the unwrapped stream, the rest through
   `console.report_result`; exit 1 on failure.

No path outside `paths.folder` is read by any tx rule in this PRD, and no
backend is called.

## Reuse inventory

- `buvis.pybase.zettel...markdown.MarkdownZettelFileParser.parse`: raw parse
  to `ZettelData`; repeated backmatter keys arrive as a list.
- `buvis.pybase.zettel...MarkdownZettelFormatter.format`: the one writer;
  `TOP_KEYS` already gives the bim key order.
- `CreateZettelUseCase` (`prepare`, `execute`): id, date, collision bump,
  exclusive create; accepts any object with `name`, `questions`, `build_data`,
  `hooks` and an optional `folder`.
- `bim.dependencies.get_repo`: the repository `new` saves through.
- `buvis.pybase.filesystem.atomic_write_text`: `--out` writes.
- `buvis.pybase.result.CommandResult`, `console.report_result`.
- `bim/doc_cli.py`: the group registration pattern.
- Source port input (read, not imported): `klyreon/spec/enums.py`,
  `spec/validator.py` (`_first_cycle` DFS ports as is), `commands/*.py`,
  `maintain/prune.py` `find_candidates`, `vault/paths.py`, `vault/state.py`.
- Nothing found for a tiromex folder setting, a claim index or wikilink
  parsing in bim: `rg -n "tiromex|concept-type|claims" src/tools/bim src/lib`
  (no hits; control `rg -n "path_zettelkasten" src/tools/bim` hits), and
  `rg -n "\[\[" src/tools/bim/shared/vault_links.py` shows only contact and
  daily-log link writers, no parser for backmatter links.

## Alternatives considered

1. **Smallest diff: move the klyreon spec package into bim unchanged** (own
   parser, writer, `Document`, frontmatter `links`/`sources`). Rejected: it
   keeps a second persisted model and a second YAML loader, and its notes
   would not survive `bim format`, which the PRD forbids.
2. **Chosen: a thin tx layer over `ZettelData`** with the rules as functions
   over a read view. Larger than option 1 only by the link and source
   readers; it buys one format, `bim query/show/format` visibility for free,
   and no library change.
3. **Fix `format_reference` in the library so repeated backmatter keys round
   trip, and write one line per link.** Closer to Dataview's own multi-value
   form, but it changes `src/lib/` behaviour for every bim note, which the
   PRD's premise risk tells this PRD not to do. Kept as a follow-up; the
   reader already accepts the repeated form, so a later switch needs no
   migration of the reader.

## Risks & edge cases

- **`bim format` and repeated backmatter keys** (existing library defect): a
  hand-written note with two `- supports::` lines is flattened to a Python
  list literal by `bim format`. tx never writes that form; the reader still
  accepts it. Reported to the owner as a separate bug, not fixed here.
- **Backmatter separator.** Discovery M5 reads "tiromex notes are bim notes
  ... backmatter after the last `---`". bim's two parsers (Python
  `extract_reference`, Rust `parser/back_matter.rs`) both split at the first
  `---` line after the front matter, so in every note bim can read, the
  separator is the only `---` line of the body and is therefore the last one.
  The contract here is bim's: a tiromex body holds no `---` line of its own.
  A note that breaks this gets `parse-error`; a test pins it; the format spec
  and the SKILL section state the rule. Last-separator parsing would change
  both parsers for every bim note and is not part of this PRD (reported to
  the owner as a possible follow-up).
- **Duplicate H1** (existing bim defect, probe 2026-11-16): a note whose
  body is only an H1, followed by backmatter, gets a second H1 from
  `bim format` and from any repository save. It hits every bim note of that
  shape, today. tx stays clear of it by contract: `empty-body` requires a
  body line on concept and index notes, and `tx new` writes no backmatter. A
  test formats the H1 + body line + `- parent::` shape and finds one H1.
  Reported to the owner as a separate bug; not fixed here (PRD Risks: report,
  do not widen).
- **Section splitting is lossy** (existing bim defect, same probes): a body
  line with ` # ` in the middle, or text before the first heading, is
  damaged by `bim format`. tx rules read the raw body, so validation is not
  fooled; the formatter damage itself is bim-wide. Reported to the owner.
- **Title fixers**: bim capitalises the first letter of a new title, so the
  starter claim statement (the title as typed) can differ from the stored
  title by case. Harmless; the test pins it.
- **`wiki-article`**: bim rewrites it to `note` on load. `new` does not offer
  it; `type-species` still accepts it on notes that carry it.
- **Obsidian Linter**: tx output is formatter output, which the vault already
  accepts. The validator reads parsed data, so spacing changes do not matter.
- **Symlinks**: a symlinked tiromex folder that leaves the zettelkasten fails
  `resolve_tiromex`; a symlinked note that leaves the folder is skipped by
  `iter_note_files`; a link target is checked after resolution.
- **Plain agent notes** never fail beyond the four base fields, and never
  reach `collect_claims`.
- **Next changes this design must not box in**: PRD 00152 adds mirror
  resolution (hooks into `sources` and replaces `source-shape` findings with
  resolved checks, and may add a severity to `Diagnostic`); PRD 00153 adds
  `shared/state.py`, `shared/git.py` and the pending-source line (it takes
  over `tx_state_dir`, `read_last_maintain` and the git check); PRD 00154
  adds `shared/prune.py` and serve/TUI adapters over the same command
  classes. Each interim helper above is private or in one named place so the
  move is mechanical.

## Test strategy outline

- `tests/tools/bim/tx/conftest.py`: a scratch vault fixture (`tmp_path/vault/notes/tiromex`),
  `BUVIS_BIM_PATH_ZETTELKASTEN` and `XDG_STATE_HOME` set through
  `monkeypatch`, an isolated `HOME`, `BUVIS_CONFIG_DIR` pointed at an empty
  tmp directory, every other `BUVIS_BIM_*` variable removed, and note builders that write converted
  source fixtures (valid concept note, index note, run note, plain note) as
  strings. No import of the retiring package.
- `test_settings.py`: defaults, each `BUVIS_BIM_TX__*` override, unknown key
  rejected, `tiromex_folder` override.
- `test_scope.py`: `resolve_tiromex` and `confine` reject absolute, `..` and
  symlink escapes; `resolve_tiromex` refuses a tiromex folder that is a
  symlink to `.` or to a sibling folder; `iter_note_files` skips an escaping
  symlink; a plain note
  validates with base fields only; a symlinked zettelkasten gives
  `vault_root` = the parent of the real directory; an outside note with claims
  is never read: a spy on `Path.read_text` and `builtins.open` records every
  path that validate, export-claims and status open, and the test fails when
  one lies under the vault root and outside `paths.folder` (the note is also
  absent from `collect_claims`, and its bytes are unchanged).
- `test_format.py`: classify per kind; link and source readers (comma form,
  repeated-key form, comma inside a title); one test per rule id on a fixture
  broken in exactly that way, asserting that rule and no other; the
  transitive cycle; a concept note, an index note and a `tx-run` note each
  survive `serialize(parse_note(...))` with equal metadata, reference,
  `h1_titles` and `body_lines`; a concept note whose body is only the H1
  followed by a `- parent::` line has one H1 and gets `empty-body`; a body
  line `I write C# and F# code.` gives no second H1; `title: 2026` and a
  non-string tag do not crash; a 13-digit id gives `zettel-id-format` and no
  `id-created-mismatch`; a UTC date whose id matches the local wall clock
  passes; a `disagreement` doubt with no `target` passes; a body
  with a `---` rule gives `parse-error`; `as_datetime` per input type (aware
  and naive datetime, date, ISO string, junk); `format_links` drops `"` from a
  title and the result parses; a link target with `.md` or `#` gives
  `link-shape`; a link with no title, an empty title and a blank title each
  give `link-shape`; `claims: []` gives `claims-required` on a thesis and
  `claims-count` on a question; a transitive cycle whose one edge is written
  as `notes/tiromex/./<id>` is still found.
- `tests/lib/pybase/adapters/test_console_adapter.py`: `warning` and
  `failure` with `stderr=True` write to stderr and nothing to stdout
  (`capsys`); without the keyword the output is on stdout as before.
- `tests/tools/bim/test_format_note.py`: `CommandFormatNote` on a tiromex
  concept note (H1, one body line, `- parent::` and a relation line) keeps
  the concept fields, unknown keys and single-line relations, has one H1,
  and a second format is byte-identical.
- `test_commands.py`: `new` (defaults, starter claim, collision bump with two
  notes in one second, invalid input writes nothing); `validate` JSON keys and
  failure result; `export-claims` exact keys, rejected-note claims present,
  outside-tiromex claims absent, `--out` refused for the vault root, a path
  under it, a symlink alias, and `~/x.json` with HOME outside the vault and
  the working directory inside it (written to HOME, nothing created in the
  vault); validate text output and the `new` refusal keep their `[rule]`
  ids through the CLI; a warning that holds `[draft]` in a path prints
  whole; `_corroboration` with a supporter that shares the note's own
  source gives an empty set, and with another source gives that source;
  `staleness` for a missing, empty, junk, old and recent `last_maintain`;
  `status` lines, metadata and the four
  staleness texts. `-k integration`: `CliRunner` on `bim tx --help` and each
  command, `json.loads(result.stdout)` on a payload with a 300-character
  claim, the same for `export-claims` and `validate --json` on a vault that
  holds one unparseable note (the warning is on stderr), one staleness line
  per invocation, a created note visible to
  `CommandQuery` and `CommandShowNote`, the shipped `SKILL.md` holding both
  the unchanged approval rule and the tiromex exception.

## Review log

Dispatch 1 findings. Blockers were fixed in the doc. Non-blockers and
questions are recorded here; "(tightened)" marks one whose contract wording
was also made exact, because the planner copies contracts verbatim.

- blocker (fixed): export-claims and validate warnings reached stdout through
  `report_result` and broke `json.loads(stdout)`. Now stderr through
  `_warn_stderr`, with a test.
- blocker (fixed): the h1 rules read two ways and bim's parser keeps an
  H1-only body out of the section headings. Now `body_text` / `h1_titles`
  with the source regex, and a round-trip fixture.
- non-blocker (tightened): bim splits backmatter at the first `---`, not the
  last. Risk entry and test added.
- non-blocker (tightened): `format_links` had no rule for `"` and `\` in a
  title. It now removes five characters.
- non-blocker (tightened): dates could be `date`, naive or aware. One reader,
  `as_datetime`. Open: an unreadable date value gets no diagnostic.
- non-blocker (tightened): transitive-cycle keys and edges did not match, and
  the relation order was not stable.
- non-blocker (tightened): `oversized-body`, `stale-review` and the id rules
  now follow the source predicates and apply to index notes.
- non-blocker (tightened): status counters and the mean-links format.
- non-blocker (tightened): the outside-note test could not fail. Now a spy.
- non-blocker (tightened): stderr and raw-stream output had no recorded
  exception. One helper, one AGENTS.md sentence.
- non-blocker (tightened): `tx new` validates the prepared note, not the
  written one. Stated; error types listed.
- non-blocker (tightened): `model` setting dropped. Stated.
- non-blocker (tightened): test config isolation (`BUVIS_CONFIG_DIR`).
- question (tightened): prune corroboration formula.
- question (tightened): `doubt-target-shape` wording.
- question (tightened): which rules `validate_note` runs.
- question (tightened): `vault_root` with a symlinked zettelkasten.
- question (tightened): link targets with `.md` or `#` are `link-shape`
  errors.

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 11, question 5

Dispatch 2 findings (codex, gpt-6-astra; its repository reads failed, so it
judged the doc text alone). It raised six blockers. Four were fixed. Two were
judged not blocking, with evidence, and are recorded as non-blockers.

- blocker (fixed): export checked `out.expanduser().resolve()` but wrote the
  raw `out`. One `dest` now serves the check, the mkdir and the write.
- blocker (fixed): a link target with `./` or an inner symlink passed the
  existence check but dropped out of the cycle graph. Edges are now resolved
  through `confine`.
- blocker (fixed): `claims: []` passed on question and example notes. Now
  `claims-count` (1 to 3 when present).
- blocker (fixed): untitled wikilinks passed. A blank title is `link-shape`.
- non-blocker (raised as blocker): backmatter splits at the first `---`, not
  the last. Not blocking: every note tx writes has one separator, so tx
  output meets the PRD wording; the gap is hand-written bodies with a `---`
  rule, which get a clear `parse-error`. Last-separator parsing is a change
  to `src/lib/` for every bim note, which the PRD Risks section tells this
  PRD to report and not widen into. Reported to the owner.
- non-blocker (raised as blocker): `_warn_stderr` builds a Rich console
  outside the adapter. Not blocking: `ConsoleAdapter` has no stderr method
  (`rg -n stderr src/lib/buvis/pybase/adapters/console/console.py`: no hit),
  the source does the same (`src/tools/klyreon/cli.py:40`), and AGENTS.md
  already handles machine-read payloads with named exceptions
  (`bim create --json`). A stderr method on the adapter is the better end
  state; it is a library change outside this PRD's file list. Reported to
  the owner.

dispatch 2 (codex): cardinal-sin 0, blocker 4, non-blocker 2, question 0

Dispatch 3 findings (codex verification, doc text alone again). It confirmed
the export fix and raised the two dispatch-2 items again as blockers.

- blocker (fixed): stderr outside the console adapter. The adapter now gets a
  `stderr` keyword on `warning` and `failure`; tx builds no Rich console.
  This is the one `src/lib/` edit, additive, with its own test.
- blocker (resolved by contract, not by a parser change): last separator.
  Discovery M5 defines tiromex notes as bim notes, and both bim parsers split
  at the first `---` line of the body. The design now states the rule (no
  `---` line in a tiromex body), validates it (`parse-error`), tests it and
  documents it. The reviewer asked for a parser change or a requirement
  change; the author judged the M5 text met and flags the judgment to the
  owner in the hand-off.
- non-blocker (tightened): a directory passed the dangling checks. Now
  `is_file()`, and doubt targets must end with `.md`.
- non-blocker (tightened): stray or reversed members markers passed.

dispatch 3 (codex): cardinal-sin 0, blocker 2, non-blocker 2, question 0

Extra review (claude, outside the three dispatches: started as a fallback
when the wait helper reported codex done too early; it read the doc as it was
before the dispatch-2 fixes and had repository access). Folded in after
dispatch 3. 2 blockers, 9 non-blockers, 4 questions.

- blocker (fixed): a tiromex folder that is a symlink to the zettelkasten or
  to a sibling folder passed `resolve_tiromex`. Now refused.
- blocker (fixed): `bim format` writes a second H1 into an H1-only body with
  backmatter (confirmed by an own probe). New rule `empty-body`; the "same
  bytes" claim is gone; the format test uses a shape with a body line.
- non-blocker (tightened): body rules read the raw body (`TxNote.body`), not
  the lossy sections.
- non-blocker (tightened): `report_result(literal=True)`; a per-command
  rendering table.
- non-blocker (tightened): stderr messages are escaped.
- non-blocker (tightened): `--out` refusal compares files (`samefile`), which
  catches case and firmlink aliases.
- non-blocker (tightened): enum membership through value sets; `str()` on
  title, tags and id; claim rows are strings.
- non-blocker (tightened): `id-created-mismatch` is skipped after
  `zettel-id-format`, and accepts the local-zone wall clock.
- non-blocker (tightened): the prune corroboration clause cannot decide yet;
  tested as a pure helper.
- question (tightened): a `disagreement` doubt with no `target` is valid.
- question (tightened): `staleness` returns a reason; empty string is never.
- already fixed after dispatch 2: export path, empty claims, untitled links.
