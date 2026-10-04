#!/usr/bin/env python3
"""Data-level parity gate: postup collector vs the ``brief-portfolio`` skill.

PRD 00070 (postup G2 — brief-portfolio cutover). This is the evidence gate that
must pass before the parallel ``brief-portfolio`` skill is deleted: postup's
collector must cover every per-repo signal field the skill's collector produces,
over the same portfolio snapshot.

The comparison is deliberately **structural, not semantic on content**:

* Per-repo *signal fields* are compared for coverage — a field the skill emits
  and postup does not is a parity failure that names the exact absent field.
* Naming/shape differences are allowed and recorded as a naming map, not a gap
  (both collectors happen to share names today, but the map is explicit so a
  future rename is a documented mapping rather than a silent break).
* Narrative and epic *content* are excluded (LLM nondeterminism). Enrichment is
  compared *structurally only*: a schema-valid ``epics.json`` exists → covered;
  a missing or schema-invalid ``epics.json`` → gap.
* A genuine repo-set difference (gita registry vs postup's roots scan) is a
  CONFIG NOTE, not a parity failure.

Two entry points:

* :func:`compare` / :func:`render_checklist` — pure functions, exercised by the
  fixture pair in ``tests/tools/postup/test_parity.py``.
* :func:`main` — the real-portfolio run: collect with both, compare, write the
  recorded checklist artifact under ``dev/local/audit-results/``.

The module has no side effects at import time and does not delete anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- The signal contract -----------------------------------------------------

# Per-repo signal fields the gate checks, keyed by the postup field name with
# the skill's field name as the value. When the names match, the map is an
# identity entry; where they differ, the entry documents the rename. Any field
# in this set that the skill emits (non-null) for a repo but postup omits is a
# parity gap naming that field.
PER_REPO_SIGNAL_MAP: dict[str, str] = {
    "releases": "releases",
    "last_tag": "last_tag",
    "unreleased_commits": "unreleased_commits",
    "issues": "issues",
    "prs": "prs",
    "ci": "ci",
    "security": "security",
    "branches": "branches",
    "prds": "prds",
    "local": "local",
    "commits": "commits",
    "commit_count": "commit_count",
    "changelog_unreleased": "changelog_unreleased",
    "brush_last_run": "brush_last_run",
    "description": "description",
    "stars": "stars",
    "language": "language",
    "default_branch": "default_branch",
}

# Nested per-signal sub-fields that must also be covered (the PRD calls these
# out explicitly for branches, prds, and local). skill sub-field -> postup.
NESTED_SIGNAL_MAP: dict[str, dict[str, str]] = {
    "branches": {"stray": "stray", "worktrees": "worktrees"},
    "prds": {"backlog": "backlog", "wip": "wip", "done_count": "done_count"},
    "local": {
        "branch": "branch",
        "dirty": "dirty",
        "dirty_since_days": "dirty_since_days",
        "ahead": "ahead",
        "behind": "behind",
        "stashes": "stashes",
    },
}

# Portfolio-level (not per-repo) signal: the external "my PRs" section.
EXTERNAL_SIGNAL_MAP: dict[str, str] = {
    "review_requested": "review_requested",
    "authored": "authored",
}

# Skill-only per-repo keys that are deliberately NOT part of the gate: either a
# duplicate of another field, or a signal the cutover accepts dropping. Recorded
# in the checklist as documented non-gaps so the reader knows they were seen.
SKILL_ONLY_ACCEPTED: dict[str, str] = {
    "org": "duplicate of owner",
    "visibility": "not carried by postup; not a portfolio-brief signal",
    "pushed_at": "not carried by postup; commit window covers recency",
    "purge_last_run": "dev/tmp trash hygiene, out of portfolio-brief scope",
    "comments": "issue engagement detail, not a coverage signal",
    "reactions": "issue engagement detail, not a coverage signal",
    "milestone": "issue milestone detail, not a coverage signal",
}


@dataclass
class RepoParity:
    """Per-repo coverage result."""

    slug: str
    missing: list[str] = field(default_factory=list)
    covered: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing


@dataclass
class ParityResult:
    """The full comparison result.

    Attributes:
        repos: Per-repo coverage for the repos present in BOTH outputs.
        skill_only_repos: repos the skill collected that postup did not (config
            note candidate — a repo-set difference, not a field gap).
        postup_only_repos: repos postup collected that the skill did not.
        external_missing: portfolio-level external signal fields postup omits.
        enrichment_covered: whether a schema-valid epics.json is present.
        enrichment_note: why enrichment is/ isn't covered.
        naming_map: the recorded skill->postup naming map (non-identity only).
        skill_repo_set / postup_repo_set: the repo slugs each side collected.
    """

    repos: list[RepoParity] = field(default_factory=list)
    skill_only_repos: list[str] = field(default_factory=list)
    postup_only_repos: list[str] = field(default_factory=list)
    external_missing: list[str] = field(default_factory=list)
    enrichment_covered: bool = False
    enrichment_note: str = ""
    naming_map: dict[str, str] = field(default_factory=dict)
    skill_repo_set: list[str] = field(default_factory=list)
    postup_repo_set: list[str] = field(default_factory=list)

    @property
    def field_gaps(self) -> list[str]:
        """Flat list of ``slug: field`` gaps across all compared repos + external."""
        gaps = [f"{rp.slug}: {miss}" for rp in self.repos for miss in rp.missing]
        gaps += [f"<external>: {miss}" for miss in self.external_missing]
        if not self.enrichment_covered:
            gaps.append(f"<enrichment>: {self.enrichment_note}")
        return gaps

    @property
    def passed(self) -> bool:
        """Parity passes when no field is missing and enrichment is covered.

        A repo-set difference alone does NOT fail parity — it is a config note.
        """
        return not self.field_gaps


def _slug(repo: dict[str, Any]) -> str:
    return f"{repo.get('owner', '?')}/{repo.get('name', '?')}"


def _present(value: Any) -> bool:
    """A signal field counts as present when the collector emitted a non-null value.

    An empty list/dict is still *present* (the collector ran and found nothing);
    only ``None`` / a missing key counts as absent. This matches how both
    collectors degrade a failed signal to absence rather than an empty value.
    """
    return value is not None


def _index_by_slug(repos: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_slug(r): r for r in repos if not r.get("skipped")}


def _compare_repo(slug: str, skill_repo: dict[str, Any], postup_repo: dict[str, Any]) -> RepoParity:
    """Compare one repo's signal fields; a field the skill emits and postup omits is a gap."""
    result = RepoParity(slug=slug)
    for postup_key, skill_key in PER_REPO_SIGNAL_MAP.items():
        if not _present(skill_repo.get(skill_key)):
            continue  # skill did not emit it → nothing to cover
        if not _present(postup_repo.get(postup_key)):
            result.missing.append(postup_key)
            continue
        result.covered.append(postup_key)
        # Nested sub-fields (branches/prds/local): a sub-field the skill emits
        # and postup omits is itself a gap, named field.subfield.
        for skill_sub, postup_sub in NESTED_SIGNAL_MAP.get(postup_key, {}).items():
            skill_val = skill_repo.get(skill_key)
            postup_val = postup_repo.get(postup_key)
            if not (isinstance(skill_val, dict) and skill_sub in skill_val):
                continue
            if not (isinstance(postup_val, dict) and postup_sub in postup_val):
                result.missing.append(f"{postup_key}.{postup_sub}")
    return result


def _enrichment_covered(postup_out_dir: Path | None) -> tuple[bool, str]:
    """Structural enrichment check: a schema-valid epics.json exists.

    Content is excluded; only presence + schema validity gate the check. Returns
    (covered, note). When no out_dir is given (fixture comparison), the caller
    supplies the verdict via the postup output dict instead — see :func:`compare`.
    """
    if postup_out_dir is None:
        return False, "no postup out_dir supplied"
    epics = postup_out_dir / "epics.json"
    if not epics.is_file():
        return False, "epics.json missing"
    try:
        from postup.domain.contracts import load_portfolio_data
        from postup.domain.epics import EpicsPayload

        data = load_portfolio_data(postup_out_dir / "data.json")
        EpicsPayload.model_validate(json.loads(epics.read_text(encoding="utf-8")))
    except Exception as exc:
        return False, f"epics.json schema-invalid: {exc}"
    else:
        _ = data  # loaded to prove data.json is readable alongside epics.json
        return True, "schema-valid epics.json present"


def compare(
    skill_output: dict[str, Any],
    postup_output: dict[str, Any],
    *,
    postup_out_dir: Path | None = None,
) -> ParityResult:
    """Compare the skill's and postup's collected outputs field-by-field.

    Args:
        skill_output: The skill collector's ``data.json`` as a dict.
        postup_output: postup's ``data.json`` as a dict (PortfolioData shape).
        postup_out_dir: Optional directory holding postup's ``epics.json`` for the
            structural enrichment check. When omitted, enrichment coverage is read
            from ``postup_output['epics_present']`` (fixture-friendly): a truthy
            value means a schema-valid epics.json exists.

    Returns:
        A :class:`ParityResult`. ``passed`` is True iff no signal field the skill
        emits is absent from postup and enrichment is structurally covered; a
        repo-set difference alone is recorded, not failed.
    """
    skill_repos = _index_by_slug(skill_output.get("repos", []))
    postup_repos = _index_by_slug(postup_output.get("repos", []))

    result = ParityResult(
        skill_repo_set=sorted(skill_repos),
        postup_repo_set=sorted(postup_repos),
        naming_map={p: s for p, s in PER_REPO_SIGNAL_MAP.items() if p != s},
    )
    result.skill_only_repos = sorted(set(skill_repos) - set(postup_repos))
    result.postup_only_repos = sorted(set(postup_repos) - set(skill_repos))

    for slug in sorted(set(skill_repos) & set(postup_repos)):
        result.repos.append(_compare_repo(slug, skill_repos[slug], postup_repos[slug]))

    skill_ext = skill_output.get("external") or {}
    postup_ext = postup_output.get("external") or {}
    for postup_key, skill_key in EXTERNAL_SIGNAL_MAP.items():
        if _present(skill_ext.get(skill_key)) and not _present(postup_ext.get(postup_key)):
            result.external_missing.append(postup_key)

    if postup_out_dir is not None:
        result.enrichment_covered, result.enrichment_note = _enrichment_covered(postup_out_dir)
    elif postup_output.get("epics_present"):
        result.enrichment_covered, result.enrichment_note = True, "schema-valid epics.json present"
    else:
        result.enrichment_covered, result.enrichment_note = False, "epics.json missing"

    return result


def render_checklist(result: ParityResult, *, repo_set_source: str = "") -> str:
    """Render the recorded parity checklist artifact body (markdown).

    Args:
        result: The comparison result.
        repo_set_source: One line describing how the compared repo set was
            derived (e.g. the gita registry path), for the config-note section.

    Returns:
        The markdown artifact body.
    """
    verdict = "PASS — full coverage" if result.passed else "FAIL — gaps below block cutover"
    lines = [
        "# brief-portfolio parity checklist",
        "",
        f"**Verdict:** {verdict}",
        "",
        "PRD 00070 (postup G2). Data-level parity gate: postup collector vs the",
        "`brief-portfolio` skill collector, over the same portfolio snapshot.",
        "Narrative/epic *content* excluded (LLM nondeterminism); enrichment compared",
        "structurally (schema-valid `epics.json` present). A repo-set difference is a",
        "config note, not a failure.",
        "",
        "## Repo set",
        "",
    ]
    if repo_set_source:
        lines.append(f"Source: {repo_set_source}")
        lines.append("")
    lines.append(f"- compared (in both): {len(set(result.skill_repo_set) & set(result.postup_repo_set))}")
    lines.append(f"- skill total: {len(result.skill_repo_set)} · postup total: {len(result.postup_repo_set)}")
    lines.append("")
    if result.skill_only_repos or result.postup_only_repos:
        lines.append("### Config note — repo-set difference (NOT a parity failure)")
        lines.append("")
        if result.skill_only_repos:
            lines.append(f"- skill-only repos: {', '.join(result.skill_only_repos)}")
        if result.postup_only_repos:
            lines.append(f"- postup-only repos: {', '.join(result.postup_only_repos)}")
        lines.append("")

    if result.naming_map:
        lines.append("## Naming map (skill → postup, non-identity only)")
        lines.append("")
        lines += [f"- `{result.naming_map[p]}` → `{p}`" for p in sorted(result.naming_map)]
        lines.append("")

    lines.append("## Per-repo signal coverage")
    lines.append("")
    for rp in sorted(result.repos, key=lambda r: r.slug):
        mark = "✓" if rp.ok else "✘"
        detail = "full coverage" if rp.ok else f"MISSING: {', '.join(rp.missing)}"
        lines.append(f"- {mark} `{rp.slug}` — {detail}")
    lines.append("")

    lines.append("## Portfolio-level signals")
    lines.append("")
    ext = "full coverage" if not result.external_missing else f"MISSING: {', '.join(result.external_missing)}"
    lines.append(f"- external (my PRs): {ext}")
    enr = "✓" if result.enrichment_covered else "✘"
    lines.append(f"- {enr} enrichment (structural): {result.enrichment_note}")
    lines.append("")

    lines.append("## Accepted skill-only fields (documented non-gaps)")
    lines.append("")
    lines += [f"- `{k}` — {why}" for k, why in sorted(SKILL_ONLY_ACCEPTED.items())]
    lines.append("")

    if not result.passed:
        lines.append("## Gaps blocking cutover")
        lines.append("")
        lines += [f"- {gap}" for gap in result.field_gaps]
        lines.append("")

    return "\n".join(lines)


# --- Real-portfolio run (Phase 1) --------------------------------------------


def _run_skill_collector(out_dir: Path, *, days: int, fetch: bool) -> dict[str, Any]:
    """Run the skill's collector into ``out_dir`` and return its data.json.

    The collector path is resolved AT EXECUTION TIME (the skill layout has
    drifted): the symlink chain from ~/.claude/skills is followed to the real
    ``scripts/collect.py``.
    """
    import subprocess

    skill_link = Path.home() / ".claude" / "skills" / "brief-portfolio"
    collector = (skill_link.resolve() / "scripts" / "collect.py") if skill_link.exists() else None
    if collector is None or not collector.is_file():
        msg = f"skill collector not found (resolved from {skill_link}); premise 'skill exists' is FALSE"
        raise FileNotFoundError(msg)
    cmd = [sys.executable, str(collector), "--days", str(days), "--out", str(out_dir)]
    if not fetch:
        cmd.append("--no-git-fetch")
    subprocess.run(cmd, check=True)
    return json.loads((out_dir / "data.json").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """Run the real-portfolio parity comparison and write the checklist artifact."""
    parser = argparse.ArgumentParser(description="brief-portfolio ↔ postup parity gate")
    parser.add_argument("--skill-data", type=Path, help="pre-collected skill data.json (skip re-running the skill)")
    parser.add_argument("--postup-data", type=Path, required=True, help="postup data.json")
    parser.add_argument("--postup-out-dir", type=Path, help="postup out_dir holding epics.json (enrichment check)")
    parser.add_argument("--out", type=Path, required=True, help="checklist artifact path to write")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--no-git-fetch", action="store_true")
    parser.add_argument(
        "--skill-out", type=Path, help="out_dir to run the skill collector into (if --skill-data omitted)"
    )
    parser.add_argument("--source-note", help="override the recorded repo-set source line in the artifact")
    args = parser.parse_args(argv)

    if args.skill_data:
        skill_output = json.loads(args.skill_data.read_text(encoding="utf-8"))
        source = args.source_note or f"pre-collected skill data.json ({args.skill_data})"
    else:
        skill_out = args.skill_out or (args.out.parent / "_skill-portfolio")
        skill_output = _run_skill_collector(skill_out, days=args.days, fetch=not args.no_git_fetch)
        source = args.source_note or "skill collector over gita registry (~/.config/gita/repos.csv)"

    postup_output = json.loads(args.postup_data.read_text(encoding="utf-8"))
    result = compare(skill_output, postup_output, postup_out_dir=args.postup_out_dir)
    body = render_checklist(result, repo_set_source=source)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(body, encoding="utf-8")
    print(f"wrote {args.out} — verdict: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
