"""The ``postup collect`` command.

Orchestrates repo discovery, bounded-parallel per-repo signal collection, and
the four file-contract writes. Returns a :class:`CommandResult` for both success
and failure — the CLI adapter renders it. No ``print``/``click.echo``/logging
here, and no traceback ever reaches the user: every per-repo failure degrades
into that repo's ``errors``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from postup.adapters.gh import GhAdapter, GhError
from postup.adapters.gitrepo import GitError, GitRepoAdapter
from postup.domain.contracts import ExternalPRs, PortfolioData, RepoData, write_outputs
from postup.domain.discovery import discover_repos
from postup.domain.repofiles import (
    read_brush_last_run,
    read_changelog_unreleased,
    read_prd_pipeline,
    read_purge_last_run,
)

if TYPE_CHECKING:
    from postup.settings import PostupSettings

__all__ = ["CommandCollect"]

_MAX_WORKERS = 8
_DEFAULT_DAYS = 60


def _now_utc() -> str:
    """Return the current UTC time as an ISO-8601 string (seconds precision)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CommandCollect:
    """Collect portfolio state into the versioned file contracts.

    Args:
        settings: Resolved postup settings (roots/excludes/out_dir).
        fetch: Whether to ``git fetch`` each repo before reading (``--no-fetch``
            sets this ``False``).
        days: Commit window in days.
    """

    def __init__(self, settings: PostupSettings, *, fetch: bool = True, days: int = _DEFAULT_DAYS) -> None:
        self.settings = settings
        self.fetch = fetch
        self.days = days

    def execute(self) -> CommandResult:
        """Run the collection and write the contracts.

        Returns:
            A success result with a summary and warnings, or a failure result
            when nothing could be collected or the write failed.
        """
        warnings: list[str] = []
        repo_paths = discover_repos(self.settings, warnings)
        if not repo_paths:
            return CommandResult(
                success=False,
                error="no repositories discovered — check the 'roots' setting",
                warnings=warnings,
            )

        collected = self._collect_all(repo_paths)
        repos = [r for r in collected if not r.skipped]
        skipped = [r for r in collected if r.skipped]
        known = {f"{r.owner}/{r.name}" for r in collected}

        data = PortfolioData(
            generated_at=_now_utc(),
            since_days=self.days,
            repos=repos,
            skipped=skipped,
            external=self._collect_external(known),
        )

        out_dir = self.settings.resolved_out_dir
        try:
            write_outputs(data, out_dir)
        except OSError as exc:
            return CommandResult(success=False, error=f"failed to write outputs to {out_dir}: {exc}")

        warnings.extend(f"{r.owner}/{r.name}: {'; '.join(r.errors)}" for r in repos if r.errors)
        warnings.extend(f"skipped {r.path}: {r.skipped}" for r in skipped)
        with_errors = sum(1 for r in repos if r.errors)
        return CommandResult(
            success=True,
            output=(
                f"collected {len(repos)} repos ({len(skipped)} skipped, "
                f"{with_errors} with warnings) -> {out_dir / 'data.json'}"
            ),
            warnings=warnings,
            metadata={
                "out_dir": str(out_dir),
                "repos": len(repos),
                "skipped": len(skipped),
                "with_errors": with_errors,
            },
        )

    def _collect_all(self, repo_paths: list[Path]) -> list[RepoData]:
        """Collect every repo in a bounded thread pool.

        Any worker exception is captured into that repo's ``errors`` so one bad
        repo never aborts the run.
        """
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            return list(pool.map(self._collect_repo, repo_paths))

    def _collect_repo(self, path: Path) -> RepoData:
        """Collect the full signal set for one repository.

        A slug/remote failure marks the repo ``skipped``; any later signal
        failure lands in ``errors`` and the partial repo is still returned.
        """
        git = GitRepoAdapter(path)
        try:
            owner, name = git.slug()
        except GitError as exc:
            return RepoData(path=str(path), owner=path.parent.name, name=path.name, skipped=str(exc))

        errors: list[str] = []
        updates: dict[str, object] = {}

        if self.fetch:
            try:
                git.fetch()
            except GitError as exc:
                errors.append(f"fetch: {exc}")

        # Local-checkout signals need no default branch or network.
        updates.update(self._collect_local_files(path, errors))

        gh = GhAdapter()
        try:
            meta = gh.meta(owner, name)
        except GhError as exc:
            errors.append(f"meta: {exc}")
            return RepoData(path=str(path), owner=owner, name=name, errors=errors, **updates)

        branch = meta.default_branch
        try:
            current = git.current_branch()
        except GitError as exc:
            errors.append(f"current-branch: {exc}")
            current = branch

        updates.update(self._collect_signals(git, gh, owner, name, branch, current, errors))
        updates.update(
            default_branch=branch,
            description=meta.description,
            language=meta.language,
            stars=meta.stars,
        )
        return RepoData(path=str(path), owner=owner, name=name, errors=errors, **updates)

    def _collect_local_files(self, path: Path, errors: list[str]) -> dict[str, object]:
        """Read the pure-filesystem signals, degrading each on failure."""
        updates: dict[str, object] = {}
        for key, reader in (
            ("prds", lambda: read_prd_pipeline(path)),
            ("changelog_unreleased", lambda: read_changelog_unreleased(path)),
            ("brush_last_run", lambda: read_brush_last_run(path)),
            ("purge_last_run", lambda: read_purge_last_run(path)),
        ):
            try:
                updates[key] = reader()
            except OSError as exc:
                errors.append(f"{key}: {exc}")
        return updates

    def _collect_signals(  # noqa: PLR0913, PLR0917  # one repo's full signal set is inherently wide
        self,
        git: GitRepoAdapter,
        gh: GhAdapter,
        owner: str,
        name: str,
        branch: str,
        current: str,
        errors: list[str],
    ) -> dict[str, object]:
        """Collect every git/gh signal for one repo, degrading each on failure."""
        updates: dict[str, object] = {}
        tasks: list[tuple[str, object]] = [
            ("commits", lambda: git.commits(branch, self.days)),
            ("commit_count", lambda: git.commit_count(branch, self.days)),
            ("branches", lambda: git.branches(branch, current)),
            ("local", lambda: git.local_state(branch, current)),
            ("issues", lambda: gh.issues(owner, name)),
            ("prs", lambda: gh.prs(owner, name)),
            ("ci", lambda: gh.ci(owner, name, branch)),
            ("security", lambda: gh.security(owner, name)),
        ]
        for key, fn in tasks:
            try:
                updates[key] = fn()  # type: ignore[operator]
            except (GitError, GhError) as exc:
                errors.append(f"{key}: {exc}")

        try:
            releases = gh.releases(owner, name)
            last_tag = releases[0].tag if releases else git.last_tag(branch)
            updates["releases"] = releases
            updates["last_tag"] = last_tag
            if last_tag:
                updates["unreleased_commits"] = git.unreleased_commits(branch, last_tag)
        except (GitError, GhError) as exc:
            errors.append(f"releases: {exc}")

        return updates

    def _collect_external(self, known: set[str]) -> ExternalPRs:
        """Collect portfolio-external PRs, degrading the whole section on failure."""
        gh = GhAdapter()
        try:
            return ExternalPRs(
                review_requested=gh.external_review_requested(known),
                authored=gh.external_authored(known),
            )
        except GhError as exc:
            return ExternalPRs(error=str(exc))
