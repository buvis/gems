# bim query — Usage Examples

Tested against a real zettelkasten: 7549 zettels across `~/bim` (zettelkasten, inbox, calendar, system, reference) loaded in 0.4s. Handles files with proper YAML frontmatter, partial frontmatter, no frontmatter at all, empty files, and non-UTF-8 binary leftovers (vim undo files — warned and skipped).

## Basics

### First 10 zettels with selected columns

```bash
bim query -q '{columns: [{field: id}, {field: title}, {field: type}], output: {limit: 10}}'
```

### Defaults (id, title, date, type, tags, file_path)

```bash
bim query -q '{output: {limit: 5}}'
```

## Scanning Non-default Directories

### Query inbox (raw, unprocessed notes)

```bash
bim query -q '
source:
  directory: ~/bim/inbox
  recursive: true
columns:
  - field: title
  - field: type
  - field: tags
  - field: file_path
output:
  limit: 15
'
```

### Query everything under ~/bim

```bash
bim query -q '
source:
  directory: ~/bim
filter:
  type: {eq: project}
sort:
  - field: date
    order: desc
columns:
  - field: title
  - field: date
    format: "%Y-%m-%d"
output:
  limit: 10
'
```

### Calendar daily notes

```bash
bim query -q '
source:
  directory: ~/bim/calendar
  recursive: true
filter:
  tags: {contains: gtd/inbox}
sort:
  - field: date
    order: desc
columns:
  - field: title
  - field: date
    format: "%Y-%m-%d"
  - field: file_path
output:
  limit: 10
'
```

### System zettels

```bash
bim query -q '
source:
  directory: ~/bim/system
columns:
  - field: id
  - field: title
  - field: type
  - field: tags
'
```

## Filtering

### Single field equality

```bash
bim query -q '
filter:
  type: {eq: recipe}
columns:
  - field: title
  - field: tags
'
```

### AND — multiple conditions

Unprocessed pex projects:

```bash
bim query -q '
filter:
  and:
    - type: {eq: project}
    - tags: {contains: pex}
    - not:
        processed: {eq: true}
sort:
  - field: date
    order: desc
columns:
  - field: title
  - field: date
    format: "%Y-%m-%d"
  - field: tags
output:
  limit: 15
'
```

### OR — match any of several values

```bash
bim query -q '
filter:
  or:
    - type: {eq: cheatsheet}
    - type: {eq: procedure}
columns:
  - field: title
  - field: type
sort:
  - field: type
  - field: title
'
```

Shorter with the `in` operator:

```bash
bim query -q '
filter:
  type: {in: [cheatsheet, procedure]}
columns:
  - field: title
  - field: type
sort:
  - field: type
  - field: title
'
```

### NOT — exclude matches

Open, incomplete, unprocessed projects:

```bash
bim query -q '
filter:
  and:
    - type: {eq: project}
    - completed: {eq: false}
    - not:
        processed: {eq: true}
columns:
  - field: title
  - field: date
    format: "%Y-%m-%d"
sort:
  - field: date
    order: desc
output:
  limit: 10
'
```

### Regex — pattern matching

All vim-related zettels:

```bash
bim query -q '
filter:
  title: {regex: "[Vv]im"}
columns:
  - field: title
  - field: type
sort:
  - field: type
  - field: title
'
```

### Contains — list membership

```bash
bim query -q '
filter:
  tags: {contains: ai}
columns:
  - field: title
  - field: type
  - field: date
    format: "%Y-%m-%d"
sort:
  - field: date
    order: desc
output:
  limit: 10
'
```

### Numeric comparison — filter by ID range

Definitions created in 2025+:

```bash
bim query -q '
source:
  directory: ~/bim/zettelkasten
filter:
  and:
    - id: {gt: 20250101000000}
    - type: {eq: definition}
sort:
  - field: title
columns:
  - field: title
  - field: date
    format: "%Y-%m-%d"
  - field: tags
'
```

### Custom metadata fields

Projects with a specific `deliverable` value:

```bash
bim query -q '
source:
  directory: ~/bim
filter:
  and:
    - type: {eq: project}
    - deliverable: {eq: enhancement}
sort:
  - field: date
    order: desc
columns:
  - field: title
  - field: date
    format: "%Y-%m-%d"
  - field: deliverable
output:
  limit: 10
'
```

### Deeply nested combinators

Learning-related zettels across everything:

```bash
bim query -q '
source:
  directory: ~/bim
filter:
  and:
    - or:
        - tags: {contains: learning}
        - tags: {contains: education}
        - tags: {contains: course}
    - not:
        processed: {eq: true}
    - type: {in: [note, project, list, course]}
sort:
  - field: type
  - field: date
    order: desc
columns:
  - field: title
  - field: type
  - field: date
    format: "%Y-%m-%d"
  - expr: "len(tags)"
    label: "# tags"
output:
  limit: 15
'
```

## Sorting

### Multi-key sort

```bash
bim query -q '
filter:
  type: {eq: project}
sort:
  - field: date
    order: desc
  - field: title
columns:
  - field: title
  - field: date
    format: "%Y-%m-%d"
output:
  limit: 10
'
```

## Expression Filters

Filter expressions let you write arbitrary Python in the `expr` field instead
of field/operator pairs. The expression receives all zettel fields as local
variables and must return a truthy/falsy value.

### Basic expression filter

Zettels with more than 3 tags:

```bash
bim query -q '
filter:
  expr: "len(tags) > 3"
columns:
  - field: title
  - expr: "len(tags)"
    label: "# tags"
'
```

### Combine with field filters

Expression filters mix freely with regular field filters inside `and`/`or`/`not`:

```bash
bim query -q '
filter:
  and:
    - type: {eq: project}
    - expr: "len(tags) > 1"
    - expr: "not processed"
columns:
  - field: title
  - field: tags
'
```

### Use Python string methods

```bash
bim query -q '
filter:
  expr: "title.startswith(\"Fix\")"
columns:
  - field: title
  - field: type
'
```

### Complex logic

```bash
bim query -q '
filter:
  expr: "type == \"project\" and any(t.startswith(\"sprint\") for t in (tags or []))"
columns:
  - field: title
  - field: tags
'
```

### Multi-statement filter (exec mode)

When a single expression isn't enough, write statements that assign to `result`:

```bash
bim query -q '
filter:
  expr: |
    score = len(tags or []) * 2
    if type == "project":
        score += 5
    result = score > 6
columns:
  - field: title
  - field: type
  - expr: "len(tags)"
    label: "# tags"
'
```

## Calculated Columns (expressions)

Column expressions now use full Python eval. All existing expressions still
work, and you can also use attribute access, method calls, list comprehensions,
and any Python builtin.

### Tag count

```bash
bim query -q '
columns:
  - field: title
  - field: type
  - expr: "len(tags)"
    label: "# tags"
sort:
  - field: type
output:
  limit: 10
'
```

### Join tags into string

```bash
bim query -q '
filter:
  type: {eq: recipe}
columns:
  - field: title
  - expr: "join(\", \", tags)"
    label: categories
'
```

### Truncated file path as location

```bash
bim query -q '
source:
  directory: ~/bim
filter:
  tags: {contains: crypto}
sort:
  - field: date
    order: desc
columns:
  - field: title
  - field: type
  - field: date
    format: "%Y-%m-%d"
  - expr: "substr(file_path, 16)"
    label: location
'
```

### Uppercase type

```bash
bim query -q '
columns:
  - field: title
  - expr: "upper(type)"
    label: TYPE
output:
  limit: 5
'
```

### Python method calls on fields

With full Python eval, you can call methods directly on field values:

```bash
bim query -q '
columns:
  - expr: "title.upper()"
    label: TITLE
  - expr: "title.replace(\" \", \"-\").lower()"
    label: slug
  - expr: "\", \".join(sorted(tags)) if tags else \"\""
    label: sorted_tags
output:
  limit: 5
'
```

### List comprehensions

```bash
bim query -q '
filter:
  type: {eq: project}
columns:
  - field: title
  - expr: "[t for t in (tags or []) if t.startswith(\"sprint\")]"
    label: sprints
'
```

### Multi-statement columns (exec mode)

When a single expression won't do, write statements and assign to `result`:

```bash
bim query -q '
columns:
  - field: title
  - expr: |
      parts = (tags or [])
      result = f"{len(parts)} tags: {parts[0]}" if parts else "no tags"
    label: summary
output:
  limit: 5
'
```

### Available convenience functions

These functions from the original safe evaluator remain available as
top-level names (no need for method syntax):

`len`, `count`, `upper`, `lower`, `concat`, `join`, `substr`, `replace`,
`year`, `month`, `day`, `format_date`, `abs`, `str`, `int`

Arithmetic (`+`, `-`, `*`, `/`), comparisons, boolean logic, subscripts,
and ternary (`x if cond else y`) are also supported.

The `datetime` module is available for date operations:

```bash
bim query -q '
columns:
  - field: title
  - expr: "(datetime.datetime.now() - date).days if date else None"
    label: age_days
output:
  limit: 5
'
```

## Output Formats

### Table (default) — Rich formatted table to stdout

```bash
bim query -q '{filter: {type: {eq: recipe}}, columns: [{field: title}]}'
```

### CSV — to stdout

```bash
bim query -q '
filter:
  type: {eq: contact}
columns:
  - field: title
  - field: tags
output:
  format: csv
  limit: 10
'
```

### CSV — to file

Export all projects across ~/bim:

```bash
bim query -q '
source:
  directory: ~/bim
filter:
  type: {eq: project}
sort:
  - field: date
    order: desc
columns:
  - field: id
  - field: title
  - field: date
    format: "%Y-%m-%d"
  - field: completed
  - field: processed
  - field: deliverable
  - expr: "join(\", \", tags)"
    label: tags
output:
  format: csv
  file: all_projects.csv
'
```

### Markdown

All recipes across zettelkasten + inbox + archives:

```bash
bim query -q '
source:
  directory: ~/bim
filter:
  type: {eq: recipe}
sort:
  - field: title
columns:
  - field: title
  - field: date
    format: "%Y-%m-%d"
  - expr: "join(\", \", tags)"
    label: categories
  - expr: "substr(file_path, 16)"
    label: location
output:
  format: markdown
'
```

## Query from File

Save a query spec as YAML:

```yaml
# my_query.yaml
source:
  directory: ~/bim
filter:
  and:
    - type: {in: [project, note]}
    - tags: {contains: knowledge-management}
sort:
  - field: type
  - field: date
    order: desc
columns:
  - field: title
  - field: type
  - field: date
    format: "%Y-%m-%d"
  - expr: "join(', ', tags)"
    label: tags
output:
  format: csv
  file: km_notes.csv
```

Run it:

```bash
bim query -f my_query.yaml
```

## Filter Operators Reference

| Operator   | Description                              | Example                          |
|------------|------------------------------------------|----------------------------------|
| `eq`       | Equal                                    | `type: {eq: project}`            |
| `ne`       | Not equal                                | `type: {ne: contact}`            |
| `gt`       | Greater than                             | `id: {gt: 20240101000000}`       |
| `ge`       | Greater or equal                         | `id: {ge: 20240101000000}`       |
| `lt`       | Less than                                | `id: {lt: 20200101000000}`       |
| `le`       | Less or equal                            | `id: {le: 20200101000000}`       |
| `in`       | Value is in list                         | `type: {in: [note, project]}`    |
| `contains` | List/string contains value               | `tags: {contains: vim}`          |
| `regex`    | Regex match on string field              | `title: {regex: "^Fix"}`         |
| `expr`     | Arbitrary Python expression (bool)       | `expr: "len(tags) > 3"`          |

## Edge Cases Handled

- **Empty files** (`Untitled.md`, 0 bytes) — parsed with defaults, no crash
- **No YAML frontmatter** (raw markdown) — title from filename, type/date inferred
- **Partial frontmatter** (tags only, no title) — missing fields get defaults
- **Non-UTF-8 files** (vim `.undo` files with `.md` extension) — warned, skipped
- **Symlinked directories** (`reference/local` → iCloud) — followed and scanned
- **27k+ files in one directory tree** — loads in under a second via Rust
- **Custom metadata** (`deliverable`, `completed`, `must-wait`) — accessible as filter fields and columns
- **Mixed zettel types** (`loop` → normalized to `project`, `wiki-article` → normalized) — consistency service runs on load
