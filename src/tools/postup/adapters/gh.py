"""GitHub CLI (``gh``) delegation for per-repo forge signals.

Every method shells out to an authenticated ``gh``. A non-zero exit or missing
binary raises :class:`GhError`; the command layer degrades that into the repo's
``errors``. Alert and CI endpoints return an empty result on ``HTTP 403/404``
(the feature is disabled for that repo) rather than raising — absence, not
failure.
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from postup.domain.contracts import (
    CIRun,
    ExternalPr,
    Issue,
    PullRequest,
    Release,
    SecurityAlert,
)

__all__ = ["GhAdapter", "GhError", "RepoMeta"]

_GH_TIMEOUT = 120
_HTTP_ABSENT_RE = re.compile(r"HTTP (403|404)")
_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_FAIL_CHECKS = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
_PASS_CHECKS = {"SUCCESS", "NEUTRAL", "SKIPPED"}


class GhError(RuntimeError):
    """Raised when a ``gh`` subprocess fails or produces unusable output."""


class RepoMeta:
    """Repository metadata returned by :meth:`GhAdapter.meta`."""

    __slots__ = ("default_branch", "description", "language", "stars")

    def __init__(self, *, default_branch: str, description: str, language: str, stars: int) -> None:
        self.default_branch = default_branch
        self.description = description
        self.language = language
        self.stars = stars


def _iso_day(value: str | None) -> str | None:
    """Return the ``YYYY-MM-DD`` prefix of an ISO timestamp, or None."""
    return value[:10] if value else None


def _checks_state(rollup: list[dict[str, Any]] | None) -> str:
    """Fold a PR's ``statusCheckRollup`` into passing/failing/pending/''."""
    if not rollup:
        return ""
    states = [(c.get("conclusion") or c.get("state") or "").upper() for c in rollup]
    if any(s in _FAIL_CHECKS for s in states):
        return "failing"
    if all(s in _PASS_CHECKS for s in states):
        return "passing"
    return "pending"


class GhAdapter:
    """Run ``gh`` for one repository (and portfolio-wide external searches)."""

    def _run(self, args: list[str]) -> str:
        """Run ``gh <args>``, returning stdout.

        Raises:
            GhError: On a non-zero exit, missing binary, or timeout.
        """
        try:
            proc = subprocess.run(  # fixed argv, no shell
                ["gh", *args],
                capture_output=True,
                text=True,
                timeout=_GH_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise GhError(f"gh {args[0]}: {exc}") from exc
        if proc.returncode != 0:
            raise GhError(f"gh {args[0]}: {proc.stderr.strip()[:300]}")
        return proc.stdout

    def _api(self, path: str) -> Any:
        """Call ``gh api <path>`` and parse the JSON response."""
        return json.loads(self._run(["api", path]) or "null")

    def _api_absent_ok(self, path: str) -> Any:
        """Like :meth:`_api` but return ``[]`` on an HTTP 403/404 (feature off)."""
        try:
            return self._api(path) or []
        except GhError as exc:
            if _HTTP_ABSENT_RE.search(str(exc)):
                return []
            raise

    def meta(self, owner: str, name: str) -> RepoMeta:
        """Return repository metadata (default branch, description, stars)."""
        data = self._api(f"repos/{owner}/{name}")
        return RepoMeta(
            default_branch=data["default_branch"],
            description=data.get("description") or "",
            language=data.get("language") or "",
            stars=data.get("stargazers_count", 0),
        )

    def releases(self, owner: str, name: str) -> list[Release]:
        """Return up to five most recent non-draft releases."""
        return [
            Release(
                tag=r["tag_name"],
                name=r.get("name") or r["tag_name"],
                date=_iso_day(r.get("published_at")),
                prerelease=r.get("prerelease", False),
            )
            for r in self._api(f"repos/{owner}/{name}/releases?per_page=5")
            if not r.get("draft")
        ]

    def issues(self, owner: str, name: str) -> list[Issue]:
        """Return open issues (pull requests filtered out)."""
        items = self._api(f"repos/{owner}/{name}/issues?state=open&per_page=100")
        return [
            Issue(
                number=i["number"],
                title=i["title"],
                created=_iso_day(i.get("created_at")),
                labels=[label["name"] for label in i.get("labels", [])],
            )
            for i in items
            if "pull_request" not in i
        ]

    def prs(self, owner: str, name: str) -> list[PullRequest]:
        """Return open pull requests with review + checks state."""
        out = self._run(
            [
                "pr",
                "list",
                "-R",
                f"{owner}/{name}",
                "--limit",
                "50",
                "--json",
                "number,title,author,isDraft,createdAt,reviewDecision,labels,statusCheckRollup",
            ],
        )
        return [
            PullRequest(
                number=p["number"],
                title=p["title"],
                author=p["author"]["login"] if p.get("author") else "?",
                created=_iso_day(p.get("createdAt")),
                draft=p["isDraft"],
                review=p.get("reviewDecision") or "",
                checks=_checks_state(p.get("statusCheckRollup")),
                labels=[label["name"] for label in p.get("labels", [])],
            )
            for p in json.loads(out)
        ]

    def ci(self, owner: str, name: str, branch: str) -> list[CIRun]:
        """Return the latest run per workflow on ``branch`` (empty if disabled)."""
        payload = self._api_absent_ok(f"repos/{owner}/{name}/actions/runs?branch={branch}&per_page=20")
        runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
        latest: dict[str, CIRun] = {}
        for run in runs:  # API returns newest first
            latest.setdefault(
                run["name"],
                CIRun(
                    workflow=run["name"],
                    status=run["status"],
                    conclusion=run.get("conclusion"),
                    url=run["html_url"],
                    date=_iso_day(run.get("created_at")),
                ),
            )
        return list(latest.values())

    def security(self, owner: str, name: str) -> list[SecurityAlert]:
        """Return open dependabot + secret-scanning alerts, severity-sorted."""
        alerts: list[SecurityAlert] = [
            SecurityAlert(
                kind="dependabot",
                severity=(a.get("security_vulnerability") or {}).get("severity") or a["security_advisory"]["severity"],
                title=f"{a['dependency']['package']['name']}: {a['security_advisory']['summary']}",
                url=a["html_url"],
            )
            for a in self._api_absent_ok(f"repos/{owner}/{name}/dependabot/alerts?state=open&per_page=100")
        ]
        alerts += [
            SecurityAlert(
                kind="secret",
                severity="critical",
                title=f"leaked secret: {a.get('secret_type_display_name') or a.get('secret_type') or '?'}",
                url=a.get("html_url") or "",
            )
            for a in self._api_absent_ok(f"repos/{owner}/{name}/secret-scanning/alerts?state=open&per_page=100")
        ]
        return sorted(alerts, key=lambda a: _SEV_ORDER.get(a.severity, 9))

    def _search(self, flag: str, known_slugs: set[str]) -> list[ExternalPr]:
        """Search open PRs matching ``flag``, excluding portfolio repos."""
        out = self._run(
            [
                "search",
                "prs",
                flag,
                "--state=open",
                "--limit",
                "50",
                "--json",
                "repository,number,title,createdAt,url,isDraft",
            ],
        )
        return [
            ExternalPr(
                repo=p["repository"]["nameWithOwner"],
                number=p["number"],
                title=p["title"],
                created=_iso_day(p.get("createdAt")),
                url=p["url"],
                draft=p["isDraft"],
            )
            for p in json.loads(out)
            if p["repository"]["nameWithOwner"] not in known_slugs
        ]

    def external_review_requested(self, known_slugs: set[str]) -> list[ExternalPr]:
        """Open PRs requesting the user's review, outside the portfolio."""
        return self._search("--review-requested=@me", known_slugs)

    def external_authored(self, known_slugs: set[str]) -> list[ExternalPr]:
        """Open PRs authored by the user, outside the portfolio."""
        return self._search("--author=@me", known_slugs)
