# brief-portfolio parity checklist

**Verdict:** PASS — full coverage

PRD 00070 (postup G2). Data-level parity gate: postup collector vs the
`brief-portfolio` skill collector, over the same portfolio snapshot.
Narrative/epic *content* excluded (LLM nondeterminism); enrichment compared
structurally (schema-valid `epics.json` present). A repo-set difference is a
config note, not a failure.

## Repo set

Source: both collectors run fresh 2026-09-29 over the gita-derived set (~/.config/gita/repos.csv), --days 60 --no-fetch; postup roots=github.com/{buvis,doogat,tbouska} with the 11 non-gita repos excluded so the two sets match exactly (26 listed, 25 collected, doogat/jink skipped by both: no origin remote)

- compared (in both): 25
- skill total: 25 · postup total: 25

## Per-repo signal coverage

- ✓ `buvis/.github` — full coverage
- ✓ `buvis/cellar` — full coverage
- ✓ `buvis/claude-aegis` — full coverage
- ✓ `buvis/claude-checkup` — full coverage
- ✓ `buvis/claude-git-ferry` — full coverage
- ✓ `buvis/claude-plugins` — full coverage
- ✓ `buvis/claude-strunk` — full coverage
- ✓ `buvis/claude-warden` — full coverage
- ✓ `buvis/clusters` — full coverage
- ✓ `buvis/container-images` — full coverage
- ✓ `buvis/docs` — full coverage
- ✓ `buvis/feedback` — full coverage
- ✓ `buvis/gems` — full coverage
- ✓ `buvis/helm-charts` — full coverage
- ✓ `buvis/home` — full coverage
- ✓ `buvis/mkdocs-zettelkasten` — full coverage
- ✓ `buvis/padcosta.nvim` — full coverage
- ✓ `buvis/www-buvis-net` — full coverage
- ✓ `doogat/ddb` — full coverage
- ✓ `tbouska/bobiste` — full coverage
- ✓ `tbouska/figure-skating-guide` — full coverage
- ✓ `tbouska/playground` — full coverage
- ✓ `tbouska/renovate-config` — full coverage
- ✓ `tbouska/sap-incident-finder` — full coverage
- ✓ `tbouska/test-area` — full coverage

## Portfolio-level signals

- external (my PRs): full coverage
- ✓ enrichment (structural): schema-valid epics.json present

## Accepted skill-only fields (documented non-gaps)

- `comments` — issue engagement detail, not a coverage signal
- `milestone` — issue milestone detail, not a coverage signal
- `org` — duplicate of owner
- `purge_last_run` — dev/tmp trash hygiene, out of portfolio-brief scope
- `pushed_at` — not carried by postup; commit window covers recency
- `reactions` — issue engagement detail, not a coverage signal
- `visibility` — not carried by postup; not a portfolio-brief signal
