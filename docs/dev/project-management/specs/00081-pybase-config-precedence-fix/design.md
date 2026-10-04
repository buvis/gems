# pybase config: fix inverted precedence in the config resolver

<!-- design; migrated from PRD 00081 flat file -->

## Provenance

Found 2026-09-26 during the blind-lens review of PRD 00079 (sysup configurable
updaters): the reviewer flagged the same `reversed()` mistake in the 00079 DESIGN,
which prompted checking the shared loader, revealing the live bug already shipped
in `resolver.py`. Empirically confirmed with a probe against the real loader.
Docstring corrected in the same session; resolver fix tracked here because it is a
behavior change with all-gems blast radius that deserves its own tests, not an
inline patch. Related: PRD 00079's `load_config` must use the correct ordering
(its design already mandates an explicit `(dir_rank, stem_rank)` sort and warns
against `reversed()`).
