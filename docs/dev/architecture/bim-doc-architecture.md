# `bim doc` — Architecture and Design

**Status:** Draft v1
**Date:** 2026-05-08
**Subject:** Document processing and library management subsystem for bim

---

## 1. Context and Goals

### The problem

Documents enter Bob's life from four channels: email attachments, ScanSnap iX100 scans, direct downloads from vendor portals, and historical paper that has accumulated on disk. Each document needs to be filed predictably and retrieved easily — typically months or years later, often in pursuit of a single number on a single line.

The current state is a flat folder structure under iCloud Drive, with one folder per issuer (vendor, authority, etc.) and a deterministic filename convention based on Zettelkasten timestamps:

```
20210311083422-cez-as-7102105594.invoice.pdf
```

This filing convention works. The retrieval layer doesn't exist yet — there is no consistent way to find a document by its content, only by its filename or folder. There is also no quality control on OCR text inside scanned PDFs, no automated classification of incoming documents, and no integration with Bob's Obsidian-based knowledge management practice.

### The goal

Extend `bim` (already the home for Bob's Zettelkasten and digital-asset management) with a subsystem that:

1. **Ingests** documents from all four sources with minimal manual effort.
2. **Files** them according to the existing canonical naming convention.
3. **Indexes** each document via a dedicated zettel in the Obsidian vault containing OCR'd text and structured metadata, making the entire archive full-text searchable.
4. **Audits** the existing archive to surface inconsistencies and missing zettels, and provides operations to fix them in a reviewable, resumable way.

The end-state is a library where every document — past or future — is filed identically, has a parsable filename, has good OCR, and has a zettel that makes it findable through Obsidian.

### Constraints and decisions

- **Extends bim, does not replace it.** The new functionality is exposed under `bim doc`. Existing bim commands (`show`, `query`, `edit`, etc.) work on document zettels because document zettels are zettels.
- **Mac-resident.** All processing runs on Bob's Mac. ScanSnap requires it, Proton Mail Bridge requires it, Ollama runs there, and iCloud Drive is the storage layer. There is no plan to move the watcher to the Talos cluster.
- **Local OCR and classification.** OCRmyPDF + Tesseract for OCR (Czech + English language packs). Ollama with Qwen 2.5 for classification and field extraction. No document content leaves the Mac.
- **Manual review for ambiguity.** Below an 0.85 confidence threshold, documents land in a triage folder for human approval before being filed.
- **Configurable paths via tilde-prefix in config; expanded paths in zettels.** Configuration files use `~/...` form for portability across machines. Zettels written into the Obsidian vault use **expanded absolute paths** because Obsidian does not resolve `~/`, and broken links in the vault defeat the point of the index.

### Non-goals

- A web UI for triage. Triage happens via editing YAML files in a folder. If this becomes painful, a UI can be added later via `bim serve`.
- Cross-machine watching. The watcher runs on one Mac. Other machines can run `bim doc` CLI commands but do not have processing roles.
- Automatic supersedes detection. Updated/corrected documents arrive as fresh entries; the relationship between original and replacement is captured manually if at all.
- Migration off iCloud Drive. iCloud is accepted as the storage layer with its known quirks; the design uses staging directories to avoid sync-conflict issues.

---

## 2. Vocabulary

These terms are used precisely throughout the document. Where the codebase needs internal names, the same terms apply.

| Term | Meaning |
|------|---------|
| **Document** | A PDF (rarely an image or other format) representing a single logical artifact: an invoice, a contract, a statement, etc. |
| **Zettel** | A markdown note in the Obsidian vault with YAML frontmatter, representing a single concept or, in this subsystem, a single document. |
| **Document zettel** | A zettel whose `type: document` and which references exactly one external PDF via `file_path:`. |
| **Issuer** | The originating party of a document — vendor, authority, employer, etc. Identified by a stable slug (e.g., `cez-as`). |
| **Issuer slug** | The canonical short identifier used in folder names, filenames, and zettel frontmatter. ASCII, lowercase, hyphen-separated. |
| **Doc type** | A category from a closed, append-only list: `invoice`, `receipt`, `statement`, `contract`, `certificate`, `reminder`, `correspondence`, `other`. |
| **Source** | Where a document entered the system: `email`, `scan`, `download`, `issuer-inbox`. The source determines whether issuer is known a priori. |
| **Canonical filename** | A filename matching the strict grammar `<zk-timestamp>-<issuer-slug>-<title-or-number>.<doc-type>.<ext>`. |
| **Triage** | The state of a document the pipeline could not auto-file, awaiting human review in `_triage/`. |
| **Audit** | A read-only walk of the archive that reports inconsistencies (missing zettels, non-canonical filenames, low-confidence OCR, unknown issuers). |
| **Issuer inbox** | A `<business_root>/<issuer-slug>/inbox/` folder where a human can place documents known to be from that issuer for processing. |
| **Triage folder** | `<business_root>/_triage/`, holding documents the pipeline produced proposals for but couldn't auto-file. |
| **Kartotéka** | Internal codename for the document subsystem (Czech for "card index"). Optional; the user-visible name is `bim doc`. |

---

## 3. Filesystem Layout

### The Business folder

Lives under iCloud Drive. Path is configurable; the default convention is:

```
~/Library/Mobile Documents/com~apple~CloudDocs/Business/
├── _triage/                          # documents awaiting human review
│   ├── 20260504093422-unknown.invoice.pdf
│   └── 20260504093422-unknown.invoice.pdf.proposed.yml
│
├── cez-as/                           # one folder per issuer
│   ├── inbox/                        # issuer-tagged manual queue
│   │   └── (any pdfs dropped here are processed with issuer pre-set)
│   ├── 20210311083422-cez-as-7102105594.invoice.pdf
│   ├── 20210315120000-cez-as-2021-Q1.statement.pdf
│   └── ...
│
├── plzensky-prazdroj/
│   ├── inbox/
│   └── ...
│
└── ...
```

Folders prefixed with `_` are infrastructure (currently just `_triage`). All other top-level folders are issuers and are expected to be present in `issuers.yml`. Audit reports any folder not registered.

Each issuer folder always contains an `inbox/` subfolder. The watcher creates it when an issuer is registered; the audit reports if it's missing.

### The Obsidian vault

Document zettels live in a dedicated subfolder. The vault layout **mirrors the business-folder layout** one-for-one: a per-issuer subfolder under `documents/`, named with the same canonical slug as the matching `<business_root>/<issuer-slug>/` directory:

```
~/Library/Mobile Documents/iCloud~md~obsidian/<vault>/
└── Zettelkasten/
    └── documents/
        ├── cez-as/
        │   ├── 20210311083422-cez-as-7102105594.invoice.md
        │   └── 20210315120000-cez-as-2021-Q1.statement.md
        ├── plzensky-prazdroj/
        │   └── ...
        └── ...
```

The zettel basename still matches the PDF basename exactly (sans the `.pdf → .md` extension swap). Cross-references via Obsidian wikilinks remain trivial because Obsidian resolves `[[<basename>]]` by basename across the vault regardless of folder depth, so existing links keep working when a zettel moves into its issuer subfolder.

**Why the mirror.** The business folder is the canonical organisational structure; mirroring it in the vault means a `cez-as/` filesystem browse, an `issuer/cez-as` tag query, and a `documents/cez-as/` Obsidian sidebar entry all surface the same set. Orphan detection stays straightforward (zettels and PDFs pair 1:1 by basename within the corresponding issuer subfolder).

### Dotfiles and configuration

Under Bob's existing dotfiles management with transparent git encryption:

```
~/.dotfiles/bim/
├── config.yml                        # bim config including [doc] section
├── issuers.yml                       # decrypted by git filter on checkout
└── issuers.yml.example               # sanitized template
```

`issuers.yml` looks decrypted to all processes. Encryption concerns are handled at the dotfile-management layer.

### State directory

Local-only operational state, never synced anywhere:

```
~/.local/state/bim/doc/               # XDG_STATE_HOME-compliant; matches sysup precedent
├── state.db                          # sqlite: sha256 dedup, processing log, watcher heartbeat
├── inbox/
│   ├── email/                        # populated by IMAP poller
│   ├── scans/                        # ScanSnap profile target
│   └── downloads/                    # browser download landing zone
├── originals/                        # pre-modification backups before re-OCR
│   └── <timestamp>-<sha256>.pdf
├── audit/
│   └── 2026-05-04T1430.json          # historical audit reports
└── log/
    └── doc.log
```

Honours `XDG_STATE_HOME` if set; otherwise defaults to `~/.local/state/bim/doc/`. This matches `src/tools/sysup/commands/nvim/nvim.py` which already reads `XDG_STATE_HOME`. Bob did not approve a `~/.kartoteka` helper dir; the dotfile-style root is rejected in favour of the XDG convention.

---

## 4. Configuration

### bim config additions

The `[doc]` section in `~/.dotfiles/bim/config.yml`:

```yaml
doc:
  paths:
    business_root: ~/Library/Mobile Documents/com~apple~CloudDocs/Business
    vault_root: ~/Library/Mobile Documents/iCloud~md~obsidian/MyVault
    vault_documents_subdir: Zettelkasten/documents
    state_dir: ~/.local/state/bim/doc
    inbox_scans: ~/.local/state/bim/doc/inbox/scans
    inbox_email: ~/.local/state/bim/doc/inbox/email
    inbox_downloads: ~/Downloads/kartoteka-inbox
    issuers_file: ~/.dotfiles/bim/issuers.yml
    originals_dir: ~/.local/state/bim/doc/originals
    originals_retention_days: 30

  ocr:
    engine: ocrmypdf
    languages: [ces, eng]
    oversample: 400
    deskew: true
    rotate_pages: true
    redo_on_low_confidence: true
    low_confidence_threshold: 0.70
    skip_text: true                   # don't re-OCR docs that already have text

  classifier:
    backend: ollama
    endpoint: http://localhost:11434
    primary_model: qwen2.5:7b-instruct
    fallback_model: qwen2.5:14b-instruct
    triage_threshold: 0.85
    max_retries: 2

  email:
    enabled: true
    imap_host: 127.0.0.1
    imap_port: 1143                   # Proton Bridge default
    imap_user: bob@bobiste.cz
    password_command: security find-generic-password -s proton-bridge -a bob@bobiste.cz -w
    watched_label: Inbox/Docs
    poll_interval_seconds: 300
    processed_action: move_to
    processed_target: Processed/Docs
    attachment_mime_types: [application/pdf, image/jpeg, image/png]

  zettel:
    ocr_text_in_body: true
    ocr_text_collapsible: true
    ocr_text_max_chars: 0             # 0 = unlimited

  watcher:
    enabled: true
    heartbeat_interval_seconds: 60
    triage_promote_on_save: true      # require approved: true in proposed.yml
```

### `issuers.yml` schema

```yaml
version: 1

# Closed, append-only list. Adding entries is fine; removing or renaming
# requires a deliberate migration.
doc_types:
  - invoice
  - receipt
  - statement
  - contract
  - certificate
  - reminder
  - correspondence
  - other

# Reserved slugs that cannot be used for issuers
reserved_slugs:
  - unknown
  - _triage
  - _config

issuers:
  cez-as:
    display_name: ČEZ a.s.
    aliases:
      - ČEZ
      - ČEZ Prodej
      - ČEZ Distribuce
      - cez.cz
      - skupinacez.cz
    notes: |
      Primary energy supplier. Monthly invoices, quarterly statements.

  plzensky-prazdroj:
    display_name: Plzeňský Prazdroj, a.s.
    aliases:
      - Pilsner Urquell
      - prazdroj.cz
```

**Key design points:**

- `doc_types` is global and not repeated per issuer.
- `aliases` lets a single canonical slug match many name variants encountered in the wild. The classifier prompt includes the alias list and is instructed to map any matching variant to the canonical slug.
- `notes` is freeform and never parsed by the system; it's for Bob.
- `reserved_slugs` prevents accidental creation of folders that would collide with infrastructure.

---

## 5. Canonical Naming and Zettels

### Filename grammar

```
<zk-timestamp>-<issuer-slug>-<title-or-number>.<doc-type>.<ext>
```

- `<zk-timestamp>`: 14-digit `YYYYMMDDhhmmss`. For ingested-now documents, this is wall-clock time of ingestion to the second. For historical documents being backfilled, it's the document date with `000000` time, with collision handling via incremented seconds if needed.
- `<issuer-slug>`: must exist in `issuers.yml` (or be approved via `register_issuer: true` in triage).
- `<title-or-number>`: slugified document number if present, otherwise slugified title, otherwise this is a triage condition.
- `<doc-type>`: one of the values in `issuers.yml:doc_types`.
- `<ext>`: the file extension, typically `pdf`.

Example: `20210311083422-cez-as-7102105594.invoice.pdf`

### Slugification rules

A single canonical function, used everywhere:

1. Apply Unicode NFKD normalization.
2. Transliterate to ASCII via `unidecode` (so `ČEZ` → `cez`, `Plzeňský` → `plzensky`).
3. Lowercase.
4. Replace any run of non-`[a-z0-9]` characters with a single hyphen.
5. Strip leading/trailing hyphens.
6. Collapse repeated hyphens.

This is non-reversible (information loss on diacritics and case), which is fine — the original strings are preserved in zettel frontmatter where retrieval needs them.

Example: `Plzeňský Prazdroj, a.s.` → `plzensky-prazdroj-a-s` → manually shortened to `plzensky-prazdroj` if Bob prefers (issuer slug is human-curated, not always pure slugification output).

### Zettel frontmatter schema

```yaml
---
id: 20210311083422
title: ČEZ a.s. invoice 7102105594
type: document
doc-type: invoice
issuer: ČEZ a.s.
doc-number: 7102105594
doc-date: 2021-03-11
doc-amount: 4218
doc-currency: CZK
doc-language: cs
ingested-at: 2026-05-04 14:30:15+02:00
ingest-source: email
file-path: "[Open file](file:///Users/bob/Library/Mobile%20Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf)"
file-sha256: 3f4a8c2b91e7d5a6b1c2d3e4f5061728394a5b6c7d8e9f0a1b2c3d4e5f607182
ocr-engine: tesseract
ocr-mean-confidence: 0.91
extraction-method: rule:cez-invoice-2024-template:v1
tags:
  - document/invoice
  - issuer/cez-as
  - year/2021
---
```

**Field rules:**

- **Key naming.** All keys are kebab-case ASCII. No underscores. The two single-word keys (`id`, `type`, `tags`, `title`, `issuer`) stay as-is.
- **Numbers are emitted bare, never double-quoted.** `id` is a 14-digit integer (it is a Zettelkasten timestamp, which never has leading zeros in normal use). `doc-number` is whatever the document carries: an all-digit invoice number is emitted as a YAML integer; a mixed alphanumeric reference (e.g. `INV-2024-001`) becomes a YAML string but the writer does not force quotes around it. Downstream parsers in this project tolerate both shapes.
- `doc-amount` is numeric in document-currency units; never quoted.
- `doc-date` is a YAML-native calendar date (`YYYY-MM-DD`).
- `ingested-at` is a YAML-native datetime in ISO 8601 with timezone offset (PyYAML emits it as `YYYY-MM-DD HH:MM:SS±HH:MM` with a space separator; `datetime.fromisoformat` on 3.11+ parses both space- and T-separated forms). It records the wall-clock moment the zettel was written (Step 7), in the host's local timezone with the offset preserved.
- `title` is a human-readable label. The canonical form is `<issuer> <doc-type> <doc-number>` (e.g. `ČEZ a.s. invoice 7102105594`). When `doc-number` is absent, the form falls back to `<issuer> <doc-type> <document-title>` using the extracted document title; if both are absent the document is a triage condition. The same string is used as the body H1 (Section "Zettel body template" below).
- `issuer` carries the issuer's human display name (e.g. `ČEZ a.s.`). The issuer **slug** is no longer surfaced as a frontmatter field; it remains discoverable via the canonical filename and the `issuer/<slug>` tag, both of which are stable and machine-readable.
- `tags` are hierarchical for Obsidian and continue to use the slug for the `issuer/<slug>` tag.
- `file-path` is a **double-quoted Markdown link** with text `Open file` wrapping a URL-encoded `file://` URL: `"[Open file](file://<URL-encoded-absolute-path>)"`. Obsidian renders the value as a clickable link directly in the Properties pane. URL encoding uses `urllib.parse.quote(path, safe="/~")` — spaces become `%20`, tildes stay literal (RFC 3986 unreserved). Internally, `DocumentZettelFrontmatter.file_path` keeps the raw absolute path (no `~/`); the Markdown-link wrapping happens only at YAML serialisation time so in-process callers are unaffected. Obsidian-side cross-platform portability is sacrificed deliberately so that the link opens reliably on Bob's Mac.
- `file-sha256` is emitted bare (a 64-char hex string is unambiguously a YAML string and the writer does not force quotes).
- Optional fields (`doc-amount`, `doc-currency`, `doc-number`) can be `null` or absent for document types where they don't apply. When `doc-number` is absent the title falls back to the document's extracted title.
- `extraction-method` records which subsystem produced the metadata. Format:
  - `rule:<rule-id>:v<version>` — full extraction by a rule
  - `rule+llm:<rule-id>:v<version>` — partial rule + LLM completion
  - `llm:<model-name>` — LLM-only extraction
  - `manual` — produced via triage with no automated extraction
  - `filename` — parsed from canonical filename during backfill
  Emitted as a YAML plain scalar; not double-quoted even when it contains colons (`rule:foo:v1`, `llm:qwen2.5:7b-instruct`). YAML 1.1 plain scalars permit colons that are not followed by whitespace.

### Zettel body template

```markdown
# {{ title }}

{{ summary }}

## OCR text

> [!quote]- Full text
> {{ ocr-text }}
```

**Body rules:**

- **H1 matches `title` exactly.** No "—", no per-field metadata (date, amount, period). The H1 is the same string written into the YAML `title` field.
- **Source-file link lives in the `file-path` frontmatter key, not the body.** The body contains no `[Open PDF]` or `[Open file]` line. Obsidian renders the frontmatter link in the Properties pane; keeping the body free of the link makes it file-type-agnostic (PDFs, images, plain-text exports, email exports all use the same shape).
- **Summary** is a 1–3 sentence natural-language précis produced by the LLM during Step 5 extraction (see Section 6, Step 5). It replaces the previous `**Date:** … **Amount:** …` block. The frontmatter already carries the structured fields; the body's job is now to give a quick human gloss of *what the document is about* without opening the source file. When the LLM cannot produce a summary (extraction failure, retry exhausted), the body emits no summary paragraph and the document is allowed to land — it is not a triage condition by itself.
- **OCR text callout** is unchanged. The `> [!quote]-` syntax is an Obsidian collapsible callout — visually compact while keeping content searchable.

---

## 6. The Processing Pipeline

The pipeline is a sequence of steps run identically for every document regardless of source. Some steps may be skipped based on source (e.g., issuer classification when source is `issuer-inbox`) or short-circuited by a successful rule match (which can replace LLM classification and extraction entirely).

The full ordering is:

1. Dedup
2. OCR
3. **Rule extraction** (new — see Section 6.5)
4. LLM classify (skipped if rules produced complete output)
5. LLM extract (skipped if rules produced complete output)
6. Name
7. Write zettel
8. File

### Step 1: Dedup

Compute SHA-256 of the input file. Look up in `state.db`.

- **Hit:** This document was already processed. Action depends on context:
  - During ingestion: log as duplicate, write a `.duplicate.yml` sidecar pointing to the existing canonical file, leave input file in place for manual cleanup.
  - During backfill: skip silently (the existing file IS the canonical entry).
- **Miss:** Continue to Step 2. Record the hash now to prevent concurrent re-processing.

### Step 2: OCR

Invoke `ocrmypdf` with configured languages (`-l ces+eng`).

- If the PDF already has a text layer and `ocr.skip_text: true`, OCRmyPDF passes through.
- If text layer is poor quality (mean confidence below `ocr.low_confidence_threshold`) and `ocr.redo_on_low_confidence: true`, run with `--redo-ocr`.
- If no text layer, OCR with deskew and rotation enabled.
- Output is always PDF/A.
- The OCR text is extracted (via `pdftotext` or `ocrmypdf`'s `--sidecar`) for use in classification and zettel body.

### Step 3: Rule extraction

Try the rule engine before invoking the LLM. See Section 6.5 for the rule schema and engine semantics.

**For each rule** (in priority order, across all issuers):
- Evaluate match clauses against OCR text, source metadata, and original filename.
- First matching rule wins.

**Outcomes:**

- **Full match** (rule with `partial: false`, all required fields extracted): Steps 4 and 5 are skipped entirely. Record `extraction_method: rule:<rule-id>:v<version>`.
- **Partial match** (rule with `partial: true`, sets some fields like issuer): Pre-populate those fields, then proceed to Steps 4 and 5 with reduced LLM scope. Record `extraction_method: rule+llm:<rule-id>:v<version>`.
- **No match**: Proceed to Steps 4 and 5 normally. Record `extraction_method: llm:<model>`.

**Skip rule:** If source is `issuer-inbox`, only rules for that specific issuer are considered (no cross-issuer rule scanning).

### Step 4: LLM classify

*Skipped if Step 3 produced a full match.*

Send OCR text + source metadata + alias list to Ollama. Two-prompt design:

**Prompt A — issuer + type:**
```
{
  "issuer_slug": "cez-as",
  "issuer_display": "ČEZ a.s.",
  "doc_type": "invoice",
  "language": "cs",
  "confidence": 0.94
}
```

The prompt includes the full list of known issuer slugs and their aliases, with explicit instruction to map any matching variant to the canonical slug rather than inventing a new one.

**Skip rule:** If source is `issuer-inbox`, the issuer is already known; this prompt is replaced by a doc-type-only prompt with much higher expected confidence.

**Skip rule:** If source is `email` and sender domain matches an issuer alias, pre-fill issuer and ask LLM only to confirm (still gets a confidence score).

**Skip rule:** If Step 3 produced a partial match that pinned the issuer, only the doc_type is asked of the LLM.

### Step 5: LLM extract

*Skipped if Step 3 produced a full match. Reduced if Step 3 produced a partial match.*

Type-specific extraction prompt. Different schemas per `doc_type`:

- `invoice`: `{number, date, amount, currency, period, payment_due_date, summary}`
- `statement`: `{period_start, period_end, balance, currency, summary}`
- `contract`: `{counterparty, effective_date, term, signed_date, summary}`
- `receipt`: `{vendor, date, amount, currency, summary}`
- `certificate`: `{subject, issued_date, expires_date, summary}`
- `correspondence`: `{subject, date, summary}`
- `other`: `{title, date, summary}`

`summary` is a 1–3 sentence natural-language précis of the document, used as the zettel body lede (see Section 5, "Body rules"). It is **not** a required field for triage purposes — a missing summary leaves the body summary paragraph blank but does not block auto-filing. All other fields follow the per-type required list at the top of `_REQUIRED_FIELDS`.

Confidence is computed per field. Missing required fields (per type, excluding `summary`) are triage conditions.

If Step 3 partial-matched some fields, those fields are removed from the extraction schema before sending to LLM (the LLM is asked only for the remaining fields).

### Step 6: Name

Build the canonical filename from extracted fields. Required components:

- `<zk-timestamp>` — ingestion time for new docs, doc_date for backfill.
- `<issuer-slug>` — from Step 3 or 4, must exist in `issuers.yml` for auto-filing.
- `<title-or-number>` — preference order: doc_number → title → triage.
- `<doc-type>` — from Step 3 or 4.

If any required component is missing or below confidence threshold → triage.

### Step 7: Write zettel

Render the zettel frontmatter and body from the template. Write atomically to `<vault_root>/<vault_documents_subdir>/<issuer-slug>/<basename>.md`. The per-issuer subfolder mirrors the business-folder layout (Section 3, "The Obsidian vault"); it is created on demand if it does not yet exist.

The zettel is written to a temp file in the same directory, fsync'd, and renamed atomically. This ensures Obsidian never sees a half-written zettel.

The frontmatter records `extraction_method:` so that audits and forensic queries can distinguish rule-processed from LLM-processed documents.

### Step 8: File

Move the PDF from staging (`~/.local/state/bim/doc/inbox/...`) to its final location (`<business_root>/<issuer-slug>/<canonical-name>.pdf`).

The move is atomic within the iCloud Drive volume (a `rename(2)` syscall). After successful move, mark the document complete in `state.db` (including `extraction_method` for later analysis).

If any step 1-7 fails, the staging file is left in place with a `.error.yml` sidecar describing the failure. The watcher does not retry automatically; manual intervention via `bim doc retry <path>` is required.

### Source-specific variations

| Source | Dedup | OCR | Rule | LLM Classify | LLM Extract | Name | Zettel | File |
|--------|-------|-----|------|--------------|-------------|------|--------|------|
| `email` | Yes | If needed | Yes (all rules) | If no full rule match | If no full rule match | Yes | Yes | Yes |
| `scan` | Yes | Always | Yes (all rules) | If no full rule match | If no full rule match | Yes | Yes | Yes |
| `download` | Yes | If needed | Yes (all rules) | If no full rule match | If no full rule match | Yes | Yes | Yes |
| `issuer-inbox` | Yes | If needed | Yes (issuer-scoped) | If needed (type only) | If no full rule match | Yes | Yes | Yes |
| `backfill-canonical` | Skip | If needed | Skip (filename is key) | Skip | Body fields only | Skip | Yes | Skip |
| `backfill-noncanonical` | Yes | If needed | Yes (all rules) | If no full rule match | If no full rule match | Yes | Yes | Yes |

---

## 6.5. The Rule Engine

The rule engine is a deterministic, declarative layer that runs before LLM classification and extraction. For documents with stable templates (recurring vendors), rules eliminate LLM calls entirely and provide auditable, reproducible processing. For documents without matching rules, the LLM remains the fallback.

### Why rules exist

The pipeline could function with LLM-only processing — and v1 of the implementation may even start that way. Rules add four properties that LLM-only processing cannot provide:

1. **Determinism for recurring vendors.** A rule for CEZ invoices either matches or doesn't. There is no probabilistic drift across documents that share a template.
2. **Auditability.** A zettel filed by `rule:cez-invoice-2024-template:v3` records exactly which logic produced its metadata. If something is wrong, the source of the wrongness is locatable in `issuers.yml`.
3. **Calibration.** Rule confidence is binary (matched or not). LLM confidence is a soft probability that varies by document type, language, and OCR quality. Rules give the triage threshold a cleaner semantic.
4. **Learning loop.** Triage corrections become the basis for new rules. Each rule reduces future triage volume for that issuer to zero.

### Rule schema

Rules live under each issuer in `issuers.yml`:

```yaml
issuers:
  cez-as:
    display_name: ČEZ a.s.
    aliases: [ČEZ, ČEZ Prodej, cez.cz, skupinacez.cz]

    rules:
      - id: cez-invoice-2024-template
        version: 1
        priority: 100
        enabled: true
        partial: false
        match:
          ocr_contains: ["IČ: 45274649", "Faktura"]
          ocr_matches: ["Faktura č\\.\\s*(\\d{10})"]
        extract:
          doc_type: invoice
          doc_number:
            from: ocr_match
            pattern: "Faktura č\\.\\s*(\\d{10})"
            group: 1
          doc_date:
            from: ocr_match
            pattern: "Datum vystavení:\\s*(\\d{2}\\.\\d{2}\\.\\d{4})"
            group: 1
            format: "%d.%m.%Y"
          doc_amount:
            from: ocr_match
            pattern: "Celkem k úhradě:\\s*([\\d\\s]+),\\d{2}\\s*Kč"
            group: 1
            transform: strip_whitespace_to_int
          doc_currency: CZK
          doc_language: cs
        confidence: 1.0
```

**Rule fields:**

| Field | Required | Meaning |
|-------|----------|---------|
| `id` | yes | Stable, human-meaningful identifier. Used in audit logs and `extraction_method`. Convention: `<issuer>-<doctype>-<descriptor>`. |
| `version` | yes | Integer. Bumped when the rule logic changes. Old version's documents stay tagged with the old version for forensics. |
| `priority` | no (default 50) | Higher wins if multiple rules match. Use 100+ for narrow templates, 10–50 for broad fingerprints. |
| `enabled` | no (default true) | Set to `false` to disable without deleting. |
| `partial` | no (default false) | If true, this rule sets some fields and lets LLM fill the rest. |
| `match` | yes | Preconditions. ALL clauses must hold. |
| `extract` | yes (if not partial) | Field assignments. |
| `confidence` | no (default 1.0) | What confidence to record if matched. Below `triage_threshold` sends to triage even on rule match. Mostly leave at 1.0. |
| `notes` | no | Freeform. Never parsed. |

### Match clauses

All clauses in `match:` must hold for the rule to fire (logical AND). A clause is one of:

| Clause | Type | Behavior |
|--------|------|----------|
| `ocr_contains` | string \| list | Substring(s) must appear in OCR text. Case-folded and ASCII-folded for diacritics before matching. |
| `ocr_matches` | regex \| list | Regex(es) must match OCR text. PCRE syntax. |
| `original_filename_matches` | regex | Source filename must match. |
| `email_from_domain` | string \| list | Sender's domain must match. |
| `email_subject_contains` | string \| list | Email subject must contain substring(s). |
| `email_subject_matches` | regex | Email subject must match regex. |
| `pdf_text_layer_present` | bool | PDF must (or must not) have a text layer. |
| `language` | string \| list | OCR language hint must match (`cs`, `en`, etc.). |

Source-specific clauses (`email_*`, `original_filename_matches`) are silently false when the source doesn't apply (e.g., a scan has no email metadata).

### Extract specifications

The `extract:` block assigns values to canonical fields. Each field can be:

**A literal value:**
```yaml
doc_currency: CZK
doc_language: cs
```

**A regex extraction from OCR text:**
```yaml
doc_number:
  from: ocr_match
  pattern: "Faktura č\\.\\s*(\\d{10})"
  group: 1
```

**A regex extraction from filename:**
```yaml
doc_date:
  from: filename_match
  pattern: "vypis_(\\d{4})_(\\d{2})\\.pdf"
  groups: [1, 2]
  format: "year-month"
```

**An email metadata field:**
```yaml
doc_date:
  from: email_date
```

**A transform on extracted text:**
```yaml
doc_amount:
  from: ocr_match
  pattern: "([\\d\\s]+),\\d{2}\\s*Kč"
  group: 1
  transform: strip_whitespace_to_int
```

**Available transforms:**

- `strip_whitespace_to_int`: removes whitespace, parses as integer. (Handles Czech `4 218` formatting.)
- `strip_whitespace_to_decimal`: same but parses as decimal.
- `parse_date`: parses with `format` field (strftime).
- `lowercase`, `uppercase`, `strip`: text normalization.
- `slugify`: applies the canonical slug function.

Custom transforms are out of scope for v1. If a vendor needs unusual processing, the document falls through to LLM.

### Partial rules

A rule with `partial: true` sets only some fields. Use cases:

**Issuer fingerprint:**
```yaml
- id: cez-fingerprint
  partial: true
  match:
    ocr_contains: ["IČ: 45274649"]
  extract:
    issuer_slug: cez-as
    issuer_display: ČEZ a.s.
    doc_language: cs
  confidence: 1.0
```

This pins the issuer for any document containing CEZ's IČO, regardless of doc type. The LLM still runs but only for doc_type and document fields, with the issuer locked in. Useful for vendors whose document types vary (invoices, statements, reminders) but where the IČO fingerprint is unambiguous.

**Email-domain fingerprint:**
```yaml
- id: my-bank-email-fingerprint
  partial: true
  match:
    email_from_domain: "mybank.cz"
  extract:
    issuer_slug: my-bank
  confidence: 1.0
```

Cheap and reliable. Many vendors send from a stable noreply address.

### Rule precedence and conflict

When multiple rules match a document:

1. Rules with `partial: false` win over rules with `partial: true` (full extraction beats partial).
2. Among rules of the same partial-ness, higher `priority` wins.
3. Among equal-priority rules, the one defined first in `issuers.yml` wins (deterministic by file order).

If a partial rule fires AND a full rule fires, the full rule wins outright (no merging).

If two rules conflict in their effective output (e.g., both partial, both setting `issuer_slug` to different values), this is a configuration error. The audit reports it; the engine fails closed and sends the document to triage with a `rule_conflict` reason.

### IČO as a fingerprinting convention

For Czech businesses, the **IČO** (8-digit company identifier) is in every official document and is unique per company. Convention:

> Every issuer rule should include an IČO match clause where possible. This makes false positives essentially impossible, since two different companies cannot share an IČO.

```yaml
match:
  ocr_contains: ["IČ: 45274649"]   # CEZ a.s.'s IČO
```

For non-Czech issuers without an IČO equivalent, use the strongest available identifier (sender domain, registered tax ID, distinctive phrasing).

### Reserved/special fields

- `extraction-method` is set automatically by the engine, not by rules.
- `id`, `title`, `ingested-at`, `ingest-source`, `file-path`, `file-sha256` are pipeline-managed and cannot be set by rules.

Rules can only set the document-content fields. Rule YAML continues to use the **internal `snake_case` names** for these (so existing `issuers.yml` files keep working) — the writer maps them to kebab-case when serialising the zettel:

| Rule YAML key | Frontmatter key |
|---------------|-----------------|
| `issuer_slug` | (not emitted; used to compose `tags` and the canonical filename only) |
| `issuer_display` | `issuer` |
| `doc_type` | `doc-type` |
| `doc_number` | `doc-number` |
| `doc_date` | `doc-date` |
| `doc_amount` | `doc-amount` |
| `doc_currency` | `doc-currency` |
| `doc_language` | `doc-language` |

The split keeps two concerns separate: rule authors write configuration in a stable, well-known shape; the **on-disk zettel** uses Bob's preferred kebab-case shape.

### Rule lifecycle

**Creation:** Manual editing of `issuers.yml`. The dotfiles transparent-encryption layer handles the file as plaintext; rule authoring is a normal text-editing workflow. Use `bim doc rules test` (see below) during authoring to verify rules behave as expected on real documents.

**Suggestion from triage:** `bim doc rules suggest --issuer <slug>` examines recent triage events for an issuer and proposes candidate rules:

```
$ bim doc rules suggest --issuer cez-as
Found 3 documents promoted from triage for cez-as in the last 30 days.

Common patterns:
  • All 3 documents contain "IČ: 45274649" → strong issuer fingerprint
  • 3/3 contain regex "Faktura č\.\s*(\d{10})" → invoice number pattern
  • 3/3 contain regex "Datum vystavení: (\d{2}\.\d{2}\.\d{4})" → date pattern
  • 3/3 contain regex "Celkem k úhradě: ([\d\s]+),\d{2} Kč" → amount pattern

Suggested rule (write to issuers.yml):
---
- id: cez-as-invoice-suggested
  version: 1
  priority: 100
  match:
    ocr_contains: ["IČ: 45274649", "Faktura"]
    ocr_matches: ["Faktura č\\.\\s*(\\d{10})"]
  extract:
    doc_type: invoice
    doc_number: { from: ocr_match, pattern: "Faktura č\\.\\s*(\\d{10})", group: 1 }
    doc_date: { from: ocr_match, pattern: "Datum vystavení:\\s*(\\d{2}\\.\\d{2}\\.\\d{4})", group: 1, format: "%d.%m.%Y" }
    doc_amount: { from: ocr_match, pattern: "Celkem k úhradě:\\s*([\\d\\s]+),\\d{2}", group: 1, transform: strip_whitespace_to_int }
    doc_currency: CZK
  confidence: 1.0
---

Review and adjust priority/id, then add to issuers.yml. Run `bim doc rules test` to validate.
```

The suggester is advisory only — it never modifies `issuers.yml` itself. Bob always reviews and edits before adopting.

**Versioning:** When a rule's logic changes (e.g., vendor changes their template), bump `version`. Existing zettels' `extraction_method` retains the old version, so you can later query "find all CEZ invoices processed by v1" if a regression is suspected.

**Disabling:** `enabled: false` in the YAML disables a rule without deletion. Useful when a rule is suspected wrong and you want to fall back to LLM temporarily.

**Auto-disable:** Out of scope for v1. If a rule's match rate falls catastrophically, the audit will show it; manual intervention follows.

### Rule quality safeguards

Rules can be wrong in two ways:

- **False positive:** rule matches when it shouldn't (e.g., too-loose regex catches an unrelated document). Filed under wrong issuer with confident extraction. Dangerous.
- **False negative:** rule fails to match when it should (e.g., template changed). Document falls through to LLM. Less harmful — at worst, you lose the optimization.

**Tools to manage this:**

**`bim doc rules test <rule-id> --pdf <path>`**

Runs a specific rule against a specific PDF (without filing it). Reports match/no-match and what would be extracted:

```
$ bim doc rules test cez-invoice-2024-template --pdf ~/Desktop/sample.pdf
Rule: cez-invoice-2024-template (v1, priority 100)
Match clauses:
  ✓ ocr_contains "IČ: 45274649"
  ✓ ocr_contains "Faktura"
  ✓ ocr_matches "Faktura č\.\s*(\d{10})"
Result: MATCH

Extraction:
  doc_type: invoice
  doc_number: "7102105594"
  doc_date: 2024-11-15
  doc_amount: 4218
  doc_currency: CZK
  doc_language: cs
```

**`bim doc rules backtest [--rule <id>] [--issuer <slug>]`**

Runs all (or one) rules against the existing archive. Reports which documents each rule would match.

If `cez-invoice-2024-template` matches an O2 statement, that's a red flag — the rule is too loose. Run this after writing a new rule and after every rule version bump.

```
$ bim doc rules backtest --rule cez-invoice-2024-template
Tested against 1247 archived documents.

Matches: 312
  • 312 in cez-as/ ✓ (expected)
  • 0 in other issuer folders ✓

No unexpected matches.
```

If unexpected matches appear, the rule needs tightening (typically by adding more specific match clauses, often the IČO).

**`bim doc rules stats`**

Reports rule usage:

```
$ bim doc rules stats
Rule usage in last 30 days:

  cez-invoice-2024-template:    47 matches  (100% rule-extracted)
  cez-fingerprint:               12 matches  (rule + LLM)
  o2-invoice-pdf-template:       18 matches  (100% rule-extracted)
  my-bank-statement-download:     6 matches  (100% rule-extracted)

  ── overall ──
  Rule-fully-extracted:    71 / 102 documents  (70%)
  Rule-partial + LLM:      12 / 102 documents  (12%)
  LLM-only:                19 / 102 documents  (19%)
  Triage:                   5 / 102 documents  (5%)
```

This is the dashboard for rule effectiveness. Falling rates suggest a vendor changed templates; rising LLM rates suggest opportunity for new rules.

### Recommended rollout

1. **Build LLM-only first.** Implement the pipeline as in Sections 1–6 with no rules. Validate end-to-end behavior.
2. **Add the rule engine as a no-op layer.** Ship Step 3 with zero rules defined. Pipeline behavior is unchanged.
3. **Write rules for the top issuers.** After ingesting a few weeks of documents, look at `state.db` for the highest-volume issuers. Write rules for the top 5 — these pay back fastest.
4. **Use triage events as fuel.** Every triage promotion is a candidate for a rule. Run `bim doc rules suggest` periodically.
5. **Backtest after every rule change.** Don't deploy a rule without verifying it doesn't false-positive against the archive.

### What rules don't do

- **They don't replace LLM for novel documents.** First-time vendors always go through LLM (and likely triage).
- **They don't handle layout (positions, tables).** Pure text-pattern matching. If a vendor's invoice can only be parsed by spatial reasoning, it stays LLM-bound.
- **They don't run arbitrary code.** No `exec:` or scripting in rule YAML. If a vendor needs custom Python, that's a plugin (out of scope for v1).
- **They don't auto-update.** A rule that stops matching is silently outdated until you notice via stats. There is no auto-disable in v1.

---

## 7. Sources

### Email (Proton Mail Bridge)

**Setup:**
- Add `docs@bobiste.cz` as an additional address in Proton settings.
- Server-side filter: messages To: `docs@bobiste.cz` are labeled `Inbox/Docs` and skip the main inbox.
- Proton Mail Bridge runs on the Mac, exposes IMAP at `127.0.0.1:1143`.
- bim's IMAP password is retrieved via `security find-generic-password` (macOS Keychain).

**Polling logic:**
- Every `email.poll_interval_seconds`, log into Bridge, list unread messages in `email.watched_label`.
- For each message, extract attachments matching `email.attachment_mime_types`.
- Save attachments to `~/.local/state/bim/doc/inbox/email/` with a sidecar `.email.yml` containing message metadata (msgid, from, subject, date) for use in classification.
- After successful processing, perform `email.processed_action`:
  - `move_to`: move message to `email.processed_target` label.
  - `label`: add a "Processed" label, leave in place.
  - `leave`: do nothing (Seen flag is enough).

**Failure handling:**
- Bridge unreachable: log error, retry on next poll. Don't escalate; Bridge will come back when the Mac wakes.
- Attachment extraction fails: leave message unread, log error. Manual investigation needed.

### ScanSnap iX100

**Setup:**
- ScanSnap Home profile "Kartotéka":
  - Type: PC (Scan to file)
  - Save to: `~/.local/state/bim/doc/inbox/scans/`
  - Format: PDF, image-only (no OCR — ScanSnap's bundled OCR is poor on Czech)
  - Resolution: 300 DPI, color
  - Auto-rotate: on
  - Blank page detection: on
- No further configuration. Scanning produces PDFs that the watcher picks up.

**Watch logic:**
- File-system event (fswatch / watchdog) on `inbox_scans`.
- Debounce: wait 5 seconds after last write event before processing (ScanSnap may write in bursts).
- Process each new PDF through the full pipeline.

### Web downloads

**Setup:**
- Browser downloads to `~/Downloads/` as usual.
- A designated subfolder `~/Downloads/kartoteka-inbox/` is watched. Bob manually moves invoice PDFs here, or configures the browser to download here for specific patterns.

**Why not watch the whole Downloads folder?** Too noisy — installer DMGs, screenshots, casual downloads. An explicit designated folder requires one extra click but eliminates false positives.

**Optional enhancement:** A browser bookmarklet or extension that downloads-and-moves to the kartoteka inbox in one action. Out of scope for v1.

### Issuer inbox (`<business_root>/<issuer-slug>/inbox/`)

**Setup:**
- Created automatically when an issuer is registered.
- Always exists for every known issuer.

**Watch logic:**
- File-system event on every `<issuer-slug>/inbox/` directory.
- Process with `source: issuer-inbox`, issuer pre-set to the parent folder's slug.
- Skip Step 3's issuer classification (saves an LLM call and avoids errors).

**Use cases:**
- Manual filing: Bob downloads from a vendor portal, knows it's CEZ, drops it in `cez-as/inbox/`.
- Bulk migration: Bob moves historical unprocessed documents into the appropriate issuer inbox, then runs `bim doc ingest --from-inboxes`.
- Recovery: if classification gets the issuer wrong on a triage item, moving it to `<correct-issuer>/inbox/` is a quick fix.

---

## 8. Triage

Documents the pipeline cannot auto-file land in `<business_root>/_triage/` with two files: the PDF (named with a best-guess canonical name) and a `<basename>.proposed.yml` sidecar.

### `.proposed.yml` schema

```yaml
# Pipeline's proposal. Edit and set approved: true to promote.
approved: false

# Set to true when registering a new issuer not yet in issuers.yml.
register_issuer: false

issuer:
  slug: cez-as
  display_name: ČEZ a.s.
  confidence: 0.62
  alternatives:
    - { slug: cez-prodej, score: 0.31 }
    - { slug: cez-distribuce, score: 0.18 }

document:
  type: invoice
  number: "7102105594"
  date: 2021-03-11
  title: null
  amount: 4218
  currency: CZK
  language: cs

source:
  kind: email
  staging_path: ~/.local/state/bim/doc/inbox/email/abc.pdf
  email_msgid: <abc@vendor.cz>
  email_from: noreply@cez.cz
  email_subject: Vyúčtování za období 02/2021
  original_filename: invoice_7102105594.pdf
  sha256: "3f4a..."

ocr:
  engine: tesseract
  languages: [ces, eng]
  mean_confidence: 0.91
  pages: 2

triage_reasons:
  - issuer confidence below threshold (0.62 < 0.85)
  - document number format unusual

# These will become the zettel frontmatter on promote
zettel_preview:
  id: "20260504093422"
  ingest_date: 2026-05-04
  tags:
    - document/invoice
    - issuer/cez-as
    - year/2021
```

### Promotion flow

1. Bob opens `_triage/<basename>.proposed.yml` in his editor.
2. Reviews and corrects the proposal. Possible edits:
   - Fix `issuer.slug` to match an existing issuer.
   - Set `register_issuer: true` if creating a new issuer.
   - Correct `document.type`, `document.number`, etc.
3. Sets `approved: true`. Saves.
4. The watcher (or manual `bim doc promote`) detects the file modification:
   - **Validation:**
     - `approved: true` is set.
     - Either `issuer.slug` exists in `issuers.yml`, OR `register_issuer: true`.
     - All fields required for canonical naming are present.
   - **If validation fails:** log warning, leave file in place, do not act. Bob fixes and re-saves.
   - **If validation passes:**
     - If `register_issuer: true`: add entry to `issuers.yml`, create `<business_root>/<new-slug>/` and `<business_root>/<new-slug>/inbox/`.
     - Build canonical filename from approved fields.
     - Write zettel.
     - Move PDF from `_triage/` to `<business_root>/<issuer-slug>/`.
     - Delete the `.proposed.yml`.

### Concurrency safety

- `issuers.yml` is modified under a `flock(2)` on a sentinel file in `state_dir`. The watcher and any CLI command that writes to it both acquire the lock first.
- Triage items can be promoted by either the watcher (auto, on file change) or a manual `bim doc promote <path>` command. Both use the same code path.

---

## 9. Audit and Retroactive Operations

### `bim doc audit`

A read-only walk of the Business folder. Produces:

- A human-readable summary on stdout.
- A structured JSON report at `<state_dir>/audit/<iso-timestamp>.json`.

**What audit checks for each PDF:**

| Check | Pass condition |
|-------|---------------|
| Filename canonical | Matches grammar `<14digits>-<slug>-<title>.<doctype>.<ext>` |
| Issuer registered | Folder name is a key in `issuers.yml.issuers` |
| Doc type valid | Suffix is in `issuers.yml.doc_types` |
| Zettel exists | `<vault>/<doc-subdir>/<issuer-slug>/<basename>.md` exists |
| OCR present | PDF has a text layer |
| OCR quality | Mean confidence ≥ `ocr.low_confidence_threshold` |
| sha256 in state.db | Document is tracked |

**What audit checks for the rule engine:**

| Check | Pass condition |
|-------|---------------|
| Rule file syntax | All rules in `issuers.yml` parse and validate against schema |
| Rule id uniqueness | No two rules share `id` (across all issuers) |
| Regex compiles | All `pattern:` values compile as valid PCRE |
| No conflicts | No two enabled rules with same priority and overlapping match clauses |
| Rule freshness | Each enabled rule has matched at least one document in last 90 days (warning only) |

**Sample output:**

```
Audit complete. Walked 1247 documents in 23 folders.

  ✓ 423 clean
  ⚠ 612 missing zettel
  ⚠ 187 needs re-OCR (text missing or low confidence)
  ⚠  92 filename non-canonical
  ⚠  34 unknown issuer (folder not in issuers.yml)
  ⚠  18 multiple issues

Issues by issuer:
  cez-as:                 312 missing zettel, 8 needs OCR
  plzensky-prazdroj:       89 missing zettel
  cez (unknown folder):    47 documents — closest match: cez-as (0.91)
  ...

Issuer inboxes:
  cez-as/inbox:            12 unprocessed
  plzensky-prazdroj/inbox:  3 unprocessed

Triage:
  _triage:                  2 awaiting review

Rules:
  ✓ 14 rules valid (8 issuers, 0 conflicts)
  ⚠ 2 rules stale (no matches in last 90 days)
      • o2-invoice-2022-template (last match: 174 days ago)
      • my-bank-statement-old-format (last match: 102 days ago)

Watcher:
  Last heartbeat: 47 seconds ago ✓

Report: ~/.local/state/bim/doc/audit/2026-05-04T14:30:15.json
```

### Retroactive operation commands

All commands:
- Default to `--dry-run` mode showing what they would do.
- Require `--apply` to mutate.
- Read the most recent audit report (or run a fresh audit if older than 1 hour).
- Log every change to `<state_dir>/log/doc.log` with reversal info.
- Are resumable: Ctrl-C is safe; re-running picks up where it left off.

**`bim doc backfill-zettels [--issuer SLUG]`**

For every PDF without a corresponding zettel:
- If filename is canonical: extract metadata from filename + folder + OCR. No issuer/type classification needed (filename is authoritative).
- LLM call enriches body fields only (title, amount, etc.).
- Write zettel.

For non-canonical filenames: skip in this command — handled by `rename`.

**`bim doc reocr [--confidence-below N] [--missing-text-only]`**

For PDFs flagged in audit:
- Copy original to `<originals_dir>/<timestamp>-<sha256>.pdf`.
- Run `ocrmypdf --redo-ocr` (or `--force-ocr` if no text exists).
- Update zettel `OCR text` block with new content.
- Update zettel `ocr_mean_confidence` and related fields.
- After `originals_retention_days`, originals are pruned by a separate `bim doc gc-originals` command (manual or scheduled).

**`bim doc rename [--dry-run]`**

For PDFs with non-canonical filenames:
- Run full classification + extraction (same as ingestion).
- Generate proposed canonical name.
- Always go through triage — never auto-rename existing files. Bob reviews each rename in `_triage/`.

**`bim doc reconcile-issuers`**

Interactive:
```
Found unknown folder: cez/ (47 documents)
Closest issuers.yml entry: cez-as (similarity 0.91)
Action: [m]erge into cez-as / [r]egister cez as new issuer / [s]kip ? m

Merging cez/ into cez-as/...
  • Adding 'cez' to cez-as.aliases
  • Moving 47 PDFs to cez-as/
  • Renaming 47 files to use cez-as slug
  • Regenerating zettels for renamed files
  • Removing empty cez/ folder
Done.
```

**`bim doc ingest --from-inboxes`**

Walks every `<business_root>/<issuer-slug>/inbox/` and processes each PDF with `source: issuer-inbox`. Used primarily for migration.

**Rule management commands**

For completeness, the rule-related commands defined in Section 6.5 are part of the same CLI:

- `bim doc rules test <rule-id> --pdf <path>` — dry-run a rule against a specific PDF.
- `bim doc rules backtest [--rule ID] [--issuer SLUG]` — verify rules against the existing archive.
- `bim doc rules suggest --issuer SLUG` — propose rules from triage history.
- `bim doc rules stats` — usage dashboard for all rules.
- `bim doc rules list` — show all rules (id, version, enabled, last match).
- `bim doc rules validate` — check `issuers.yml` syntax and rule conflicts (also part of `bim doc audit`).

### Originals preservation

Before any operation that modifies a PDF in place (re-OCR, future enhancements):
1. Copy to `<originals_dir>/<iso-timestamp>-<original-sha256>.pdf`.
2. Record in state.db with original path and operation type.
3. After `originals_retention_days`, `bim doc gc-originals` deletes them.

This gives a 30-day rollback window for any destructive operation.

---

## 10. The Watcher

A long-running process (one instance, on Mac, managed by launchd) that drives all event-based processing.

### What it watches

- `~/.local/state/bim/doc/inbox/scans/` (filesystem events)
- `~/.local/state/bim/doc/inbox/email/` (filesystem events; populated by IMAP poller subprocess)
- `~/Downloads/kartoteka-inbox/` (filesystem events)
- `<business_root>/<issuer-slug>/inbox/` for every known issuer (filesystem events)
- `<business_root>/_triage/*.proposed.yml` (filesystem events for triage promotion)

### IMAP polling

Embedded in the watcher process. Every `email.poll_interval_seconds`:
1. Acquire lock (single concurrent IMAP session).
2. Connect to Bridge.
3. List unread in watched label.
4. For each message: download attachments to `inbox_email`, write `.email.yml` sidecar.
5. Mark message processed (move/label/leave per config).
6. Disconnect.

Failures (Bridge unreachable, network error) are logged and retried on next interval.

### Heartbeat

Every `watcher.heartbeat_interval_seconds`:
- Update a timestamp in `state.db`.
- Logged at debug level.

`bim doc audit` reports the heartbeat age. A heartbeat older than ~5× the interval is suspicious.

### launchd configuration

A user-level launchd plist in `~/Library/LaunchAgents/com.bobiste.bim.doc.plist`:
- `RunAtLoad: true`
- `KeepAlive: true` (restart on crash)
- `StandardErrorPath`, `StandardOutPath` → `<state_dir>/log/`
- Loaded at user login, runs while user is logged in, suspended when Mac sleeps.

### Lifecycle

- **Start:** `launchctl load ~/Library/LaunchAgents/com.bobiste.bim.doc.plist`
- **Stop:** `launchctl unload ~/Library/LaunchAgents/com.bobiste.bim.doc.plist`
- **Restart:** unload + load
- **Status check:** `bim doc status` reports watcher heartbeat age, queue depths, recent errors.

### Coordination with CLI

The watcher and `bim doc <command>` share state via:
- **state.db** for sha256 dedup (SQLite handles concurrent reads/writes).
- **flock on `<state_dir>/issuers.lock`** for issuers.yml modifications.
- **No coordination needed** for filesystem operations on different documents (each document has a unique path).

CLI commands that would conflict with the watcher (e.g., `bim doc reocr` on a file currently being processed) acquire a per-document lock based on sha256 before mutating.

---

## 11. Failure Modes and Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Watcher dies | Heartbeat stale in audit | launchd restarts automatically; if persistent, check log |
| Ollama unreachable | Classification step times out | Retry per `classifier.max_retries`; if still failing, write `.error.yml` and continue with next document |
| OCR fails | OCRmyPDF non-zero exit | Write `.error.yml` with stderr; document stays in staging |
| Bridge unreachable | IMAP connection error | Retry next poll cycle; log |
| issuers.yml malformed | Validation on load | Refuse to start; prompt manual fix |
| Disk full in state_dir | OS error | Halt processing, alert via log |
| iCloud sync conflict on _triage | `.proposed 2.yml` appears | Audit detects and reports; manual cleanup |
| Concurrent issuers.yml writes | flock prevents | One writer wins, other waits |
| Document sha256 collision | state.db lookup | Treated as duplicate; correct handling per source |
| Zettel basename collision | Pre-write check | Append second-counter to timestamp; log |
| Filename collision in issuer folder | Pre-move check | Same: increment timestamp; log |
| Mac asleep / off | N/A — nothing runs | Sources accumulate; processed on wake |

### Recovery commands

- `bim doc retry <path>` — re-process a staging file with `.error.yml`.
- `bim doc clear-error <path>` — delete an `.error.yml` and remove from queue.
- `bim doc status` — current state of watcher, queues, recent errors.
- `bim doc gc-originals` — prune originals older than retention.
- `bim doc verify` — walk state.db and verify every recorded sha256 still maps to a present file; report orphans.

---

## 12. Open Questions and Deferred Decisions

These are deliberately out of scope for v1 but recorded so they can be revisited.

### Open questions

1. **Zettel placement of `id` field — string or number?** Currently quoted as string for safety. Confirm against bim's existing zettel handling — if other zettels use unquoted numbers, consistency may matter.

2. **Should `bim doc audit` cache results?** A full walk of 1000+ PDFs takes time. Caching audit results with invalidation on file change could speed up repeated commands. Probably not needed initially; revisit if audit becomes slow.

3. **What about non-PDF documents?** Email attachments may include `.docx`, `.xlsx`, `.eml`. Current design accepts only PDFs and images; other formats could be converted to PDF on ingestion via LibreOffice headless. Deferred until a real document forces the issue.

4. **OCR re-runs after Tesseract upgrades.** Future Tesseract versions may produce better text. Should `bim doc reocr --all-older-than-version X` exist? Probably yes eventually; not v1.

5. **What about Czech ID/passport scans, contracts with handwritten signatures?** These don't fit the invoice/statement/contract model cleanly. The `other` doc type catches them but extraction will be poor. Worth observing real cases before designing further.

6. **Sophistication of `bim doc rules suggest`.** v1 starts with simple pattern detection (common substrings, common regex matches across triaged documents). More sophisticated approaches — e.g., asking the LLM itself to propose rules from a sample of OCR texts — could improve quality but add complexity. Defer until manual rule writing becomes a bottleneck.

7. **Cross-issuer/global rules.** All rules currently belong to a single issuer in `issuers.yml`. Some patterns might be cross-cutting (e.g., "any document with QR payment code has this date format"). Defer until a real example makes the case.

8. **Rule confidence below 1.0.** The `confidence:` field on a rule allows specifying less than full confidence, but the design currently expects 1.0 for almost all rules. If non-1.0 confidence becomes useful in practice (e.g., for fuzzy fingerprints), revisit how it interacts with the triage threshold.

### Deferred features

- **Web triage UI via `bim serve`.** Folder + YAML triage is sufficient for v1. UI may follow if the file-based flow becomes annoying.
- **Supersedes/replaces tracking.** Manual via frontmatter only. Automatic detection is too error-prone.
- **OCR text truncation in zettels.** Configurable but defaulted off. Revisit if vault performance suffers.
- **Cross-machine watcher.** Single Mac watcher only. Talos cluster integration not planned.
- **Browser extension for downloads.** Manual placement in `~/Downloads/kartoteka-inbox/` for v1.
- **Email auto-forwarding from main inbox.** If Bob receives an invoice on his main address, he forwards manually to `docs@bobiste.cz`. Auto-detection of invoices in main inbox is out of scope.
- **Mobile capture.** ScanSnap is desktop-only. iPhone scanning via Notes/Files app could feed into `inbox_downloads` via iCloud Drive but is not a designed flow.
- **Rule auto-disable on failure.** If a rule's match rate drops to zero, the system could disable it automatically. v1 reports it via audit but requires manual `enabled: false`.
- **Custom transforms in rules (Python plugins).** v1 ships a fixed set of transforms (`strip_whitespace_to_int`, etc.). Custom Python is out of scope.
- **Spatial/layout-aware rule clauses.** v1 rules operate on plain text. Position-aware extraction (cell in table, region of page) is deferred until a real vendor needs it.

---

## Appendix A: Sample Files

### Sample `issuers.yml`

```yaml
version: 1

doc_types:
  - invoice
  - receipt
  - statement
  - contract
  - certificate
  - reminder
  - correspondence
  - other

reserved_slugs:
  - unknown
  - _triage
  - _config

issuers:
  cez-as:
    display_name: ČEZ a.s.
    aliases: [ČEZ, ČEZ Prodej, ČEZ Distribuce, cez.cz, skupinacez.cz]
    notes: Energy supplier. Monthly invoices.
    rules:
      - id: cez-fingerprint
        version: 1
        priority: 50
        partial: true
        match:
          ocr_contains: ["IČ: 45274649"]
        extract:
          issuer_slug: cez-as
          issuer_display: ČEZ a.s.
          doc_language: cs
        confidence: 1.0

      - id: cez-invoice-2024-template
        version: 1
        priority: 100
        partial: false
        match:
          ocr_contains: ["IČ: 45274649", "Faktura"]
          ocr_matches: ["Faktura č\\.\\s*(\\d{10})"]
        extract:
          issuer_slug: cez-as
          issuer_display: ČEZ a.s.
          doc_type: invoice
          doc_number: { from: ocr_match, pattern: "Faktura č\\.\\s*(\\d{10})", group: 1 }
          doc_date: { from: ocr_match, pattern: "Datum vystavení:\\s*(\\d{2}\\.\\d{2}\\.\\d{4})", group: 1, format: "%d.%m.%Y" }
          doc_amount: { from: ocr_match, pattern: "Celkem k úhradě:\\s*([\\d\\s]+),\\d{2}\\s*Kč", group: 1, transform: strip_whitespace_to_int }
          doc_currency: CZK
          doc_language: cs
        confidence: 1.0

  o2-czech:
    display_name: O2 Czech Republic a.s.
    aliases: [O2, o2.cz]
    rules:
      - id: o2-email-fingerprint
        version: 1
        priority: 50
        partial: true
        match:
          email_from_domain: "o2.cz"
        extract:
          issuer_slug: o2-czech
          issuer_display: O2 Czech Republic a.s.
        confidence: 1.0

  plzensky-prazdroj:
    display_name: Plzeňský Prazdroj, a.s.
    aliases: [Pilsner Urquell, prazdroj.cz]
    # No rules yet — falls through to LLM
```

### Sample canonical filename

```
20210311083422-cez-as-7102105594.invoice.pdf
```

Decomposes as:
- `20210311083422` — Zettelkasten timestamp (March 11, 2021, 08:34:22)
- `cez-as` — issuer slug (matches `issuers.yml` entry)
- `7102105594` — invoice number from document
- `invoice` — doc type
- `pdf` — extension

### Sample document zettel

`/Users/bob/Library/Mobile Documents/iCloud~md~obsidian/MyVault/Zettelkasten/documents/cez-as/20210311083422-cez-as-7102105594.invoice.md`:

```markdown
---
id: 20210311083422
title: ČEZ a.s. invoice 7102105594
type: document
doc-type: invoice
issuer: ČEZ a.s.
doc-number: 7102105594
doc-date: 2021-03-11
doc-amount: 4218
doc-currency: CZK
doc-language: cs
ingested-at: 2026-05-04 14:30:15+02:00
ingest-source: email
file-path: "[Open file](file:///Users/bob/Library/Mobile%20Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf)"
file-sha256: 3f4a8c2b91e7d5a6b1c2d3e4f5061728394a5b6c7d8e9f0a1b2c3d4e5f607182
ocr-engine: tesseract
ocr-mean-confidence: 0.91
extraction-method: rule:cez-invoice-2024-template:v1
tags:
  - document/invoice
  - issuer/cez-as
  - year/2021
---

# ČEZ a.s. invoice 7102105594

Monthly electricity invoice for February 2021. Billing period 01.02.2021–28.02.2021. Total due 4 218 CZK, payment by 25.03.2021.

## OCR text

> [!quote]- Full text
> ČEZ a.s.
> Faktura č. 7102105594
> Datum vystavení: 11.03.2021
> Období: 02/2021
> Celkem k úhradě: 4 218,00 Kč
> ...
```

### Sample `.proposed.yml` for a triage item

```yaml
approved: false
register_issuer: false

issuer:
  slug: cez-as
  display_name: ČEZ a.s.
  confidence: 0.62
  alternatives:
    - { slug: cez-prodej, score: 0.31 }

document:
  type: invoice
  number: "7102105594"
  date: 2021-03-11
  title: null
  amount: 4218
  currency: CZK
  language: cs

source:
  kind: email
  staging_path: ~/.local/state/bim/doc/inbox/email/2026-05-04T093422-abc.pdf
  email_msgid: <abc@vendor.cz>
  email_from: noreply@cez.cz
  email_subject: Vyúčtování za období 02/2021
  original_filename: invoice_7102105594.pdf
  sha256: "3f4a8c2b91e7d5..."

ocr:
  engine: tesseract
  languages: [ces, eng]
  mean_confidence: 0.91
  pages: 2

triage_reasons:
  - issuer confidence below threshold (0.62 < 0.85)

zettel_preview:
  id: "20260504093422"
  ingest_date: 2026-05-04
  tags: [document/invoice, issuer/cez-as, year/2021]
```

### Sample audit report (JSON excerpt)

```json
{
  "version": 1,
  "generated_at": "2026-05-04T14:30:15+02:00",
  "business_root": "~/Library/Mobile Documents/com~apple~CloudDocs/Business",
  "totals": {
    "documents_walked": 1247,
    "clean": 423,
    "missing_zettel": 612,
    "needs_reocr": 187,
    "noncanonical_filename": 92,
    "unknown_issuer_folder": 34,
    "multiple_issues": 18
  },
  "by_issuer": {
    "cez-as": {
      "total": 320,
      "missing_zettel": 312,
      "needs_reocr": 8
    },
    "plzensky-prazdroj": {
      "total": 89,
      "missing_zettel": 89
    }
  },
  "unknown_folders": [
    {
      "name": "cez",
      "document_count": 47,
      "closest_match": { "slug": "cez-as", "similarity": 0.91 }
    }
  ],
  "issuer_inboxes": {
    "cez-as/inbox": 12,
    "plzensky-prazdroj/inbox": 3
  },
  "triage": {
    "_triage": 2
  },
  "watcher": {
    "last_heartbeat": "2026-05-04T14:29:28+02:00",
    "heartbeat_age_seconds": 47,
    "status": "ok"
  }
}
```

---

*End of document.*
