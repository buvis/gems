# PRD 00120 dependency blocker

PRD 00120 is blocked before design, planning, or implementation by its explicit predecessors, 00118 and 00119. Both remain in `prds/hold/`; neither shipped.

Verified current tree:

- `src/tools/bim/params/create_note.py:13–16` exposes only template, title, tags and answers; body, source and dry-run inputs from 00118 are absent.
- `src/tools/bim/note_write_cli.py:78–93` has no create `--body-file`, `--source`, `--dry-run` or `--json` options, which 00120's acceptance commands require.
- `src/tools/bim/commands/create_note/create_note.py:50–62` calls `execute` directly and returns only path metadata, without the preparation, date and wikilink contract consumed by 00120.
- `reports/00119-bootstrap.md` records the same missing 00118 foundation and 00119's verified hold.

Absorbing the prerequisite implementation would bypass 00118's held plan-expansion gate and expand this successor's scope. Use the canonical `blocking_escalation` stall, preserving both predecessors and this PRD for ordered resumption. No workers, tests, design reviewers, or completion reviewers ran. Resume 00120 only after 00118 and 00119 are implemented and verified.
