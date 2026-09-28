from __future__ import annotations

from postup.adapters.gh import GhError
from postup.adapters.gitrepo import GitError
from postup.commands.collect.collect import CommandCollect
from postup.domain.contracts import (
    Branches,
    CIRun,
    Commit,
    ExternalPr,
    Issue,
    LocalState,
    PullRequest,
    Release,
    SecurityAlert,
    load_portfolio_data,
)
from postup.settings import PostupSettings


def _make_repo(root, name, remote="buvis"):
    repo = root / name
    (repo / ".git").mkdir(parents=True)
    return repo


class FakeGit:
    """Stand-in for GitRepoAdapter keyed by the repo directory name."""

    def __init__(self, path):
        self.path = path
        self.name = path.name
        self.fetched = False

    def slug(self):
        return ("buvis", self.name)

    def fetch(self):
        self.fetched = True

    def current_branch(self):
        return "main"

    def commits(self, branch, days):
        return [Commit(sha="abc", date="2026-09-01", author="bob", subject=f"work on {self.name}")]

    def commit_count(self, branch, days):
        return 1

    def last_tag(self, branch):
        return "v1.0.0"

    def unreleased_commits(self, branch, last_tag):
        return 3

    def branches(self, branch, current):
        return Branches(stray=[], worktrees=[])

    def local_state(self, branch, current):
        return LocalState(branch=current, dirty=0, ahead=0, behind=0, stashes=0)


class FakeGh:
    def meta(self, owner, name):
        from postup.adapters.gh import RepoMeta

        return RepoMeta(default_branch="main", description="d", language="Python", stars=1)

    def releases(self, owner, name):
        return [Release(tag="v1.0.0", name="v1.0.0", date="2026-08-01")]

    def issues(self, owner, name):
        return [Issue(number=1, title="bug", created="2026-09-01")]

    def prs(self, owner, name):
        return [PullRequest(number=2, title="pr", author="bob", created="2026-09-02", checks="passing")]

    def ci(self, owner, name, branch):
        return [CIRun(workflow="Test", status="completed", conclusion="success", url="u")]

    def security(self, owner, name):
        return [SecurityAlert(kind="dependabot", severity="high", title="dep: x", url="u")]

    def external_review_requested(self, known):
        return [ExternalPr(repo="other/lib", number=9, title="review", url="u")]

    def external_authored(self, known):
        return []


def _patch_adapters(mocker, git_cls=FakeGit, gh_cls=FakeGh):
    mocker.patch("postup.commands.collect.collect.GitRepoAdapter", git_cls)
    mocker.patch("postup.commands.collect.collect.GhAdapter", gh_cls)


class TestHappyPath:
    def test_two_repos_produce_all_four_files(self, tmp_path, mocker):
        src = tmp_path / "src"
        _make_repo(src, "gems")
        _make_repo(src, "dotfiles")
        out = tmp_path / "out"
        _patch_adapters(mocker)

        settings = PostupSettings(roots=[str(src)], out_dir=str(out))
        result = CommandCollect(settings).execute()

        assert result.success
        assert (out / "data.json").is_file()
        assert (out / "commits-digest.md").is_file()
        assert (out / "history.jsonl").is_file()

        data = load_portfolio_data(out / "data.json")
        assert {r.name for r in data.repos} == {"gems", "dotfiles"}
        gems = next(r for r in data.repos if r.name == "gems")
        assert gems.commit_count == 1
        assert gems.unreleased_commits == 3
        assert gems.issues[0].number == 1
        assert gems.prs[0].checks == "passing"
        assert data.external.review_requested[0].repo == "other/lib"
        assert not gems.errors

    def test_history_line_appended(self, tmp_path, mocker):
        src = tmp_path / "src"
        _make_repo(src, "gems")
        out = tmp_path / "out"
        _patch_adapters(mocker)
        CommandCollect(PostupSettings(roots=[str(src)], out_dir=str(out))).execute()
        assert len((out / "history.jsonl").read_text().strip().splitlines()) == 1


class TestNoFetchExcludeMissingRoot:
    def test_no_fetch_skips_fetch_and_excluded_repo_absent(self, tmp_path, mocker):
        src = tmp_path / "src"
        _make_repo(src, "gems")
        excluded = _make_repo(src, "secret")
        missing = tmp_path / "nope"
        out = tmp_path / "out"

        created: list[FakeGit] = []

        class TrackingGit(FakeGit):
            def __init__(self, path):
                super().__init__(path)
                created.append(self)

        _patch_adapters(mocker, git_cls=TrackingGit)

        settings = PostupSettings(
            roots=[str(src), str(missing)],
            excludes=[str(excluded)],
            out_dir=str(out),
        )
        result = CommandCollect(settings, fetch=False).execute()

        assert result.success
        data = load_portfolio_data(out / "data.json")
        assert {r.name for r in data.repos} == {"gems"}  # excluded absent
        assert all(not g.fetched for g in created)  # --no-fetch honored
        assert any("nope" in w for w in result.warnings)  # missing root warned


class TestGhUnauthenticated:
    def test_gh_failure_degrades_into_errors_success_exit(self, tmp_path, mocker):
        src = tmp_path / "src"
        _make_repo(src, "gems")
        out = tmp_path / "out"

        class UnauthGh(FakeGh):
            def meta(self, owner, name):
                raise GhError("gh: not logged in")

        _patch_adapters(mocker, gh_cls=UnauthGh)

        result = CommandCollect(PostupSettings(roots=[str(src)], out_dir=str(out))).execute()

        assert result.success  # run still exits successfully
        data = load_portfolio_data(out / "data.json")
        gems = data.repos[0]
        assert any("meta" in e for e in gems.errors)  # error captured, no crash
        assert any("gems" in w for w in result.warnings)

    def test_per_signal_failure_captured(self, tmp_path, mocker):
        src = tmp_path / "src"
        _make_repo(src, "gems")
        out = tmp_path / "out"

        class FlakyGit(FakeGit):
            def commits(self, branch, days):
                raise GitError("git log exploded")

        _patch_adapters(mocker, git_cls=FlakyGit)
        result = CommandCollect(PostupSettings(roots=[str(src)], out_dir=str(out))).execute()

        assert result.success
        data = load_portfolio_data(out / "data.json")
        assert any("commits" in e for e in data.repos[0].errors)


class TestNoRepos:
    def test_empty_portfolio_returns_failure(self, tmp_path, mocker):
        _patch_adapters(mocker)
        result = CommandCollect(PostupSettings(roots=[str(tmp_path / "empty")], out_dir=str(tmp_path / "o"))).execute()
        assert not result.success
        assert "no repositories" in (result.error or "")
