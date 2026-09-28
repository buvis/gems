from __future__ import annotations

from postup.domain.discovery import discover_repos
from postup.settings import PostupSettings


def _make_repo(root, *parts):
    repo = root.joinpath(*parts)
    (repo / ".git").mkdir(parents=True)
    return repo


class TestDiscoverRepos:
    def test_finds_nested_repos_deduped_and_sorted(self, tmp_path):
        root = tmp_path / "src"
        _make_repo(root, "org_a", "alpha")
        _make_repo(root, "org_a", "beta")
        _make_repo(root, "org_b", "gamma")
        (root / "org_a" / "not_a_repo").mkdir()  # plain dir, ignored

        settings = PostupSettings(roots=[str(root)])
        found = discover_repos(settings)

        names = [p.name for p in found]
        assert names == ["alpha", "beta", "gamma"]  # sorted
        assert len(set(found)) == len(found)  # deduped

    def test_stops_descending_into_a_repo(self, tmp_path):
        root = tmp_path / "src"
        outer = _make_repo(root, "outer")
        # a nested .git inside a repo must not be discovered as a second repo
        (outer / "vendor" / ".git").mkdir(parents=True)

        found = discover_repos(PostupSettings(roots=[str(root)]))
        assert [p.name for p in found] == ["outer"]

    def test_excludes_drop_matching_repos(self, tmp_path):
        root = tmp_path / "src"
        _make_repo(root, "keep")
        dropped = _make_repo(root, "drop")

        settings = PostupSettings(roots=[str(root)], excludes=[str(dropped)])
        found = discover_repos(settings)
        assert [p.name for p in found] == ["keep"]

    def test_missing_root_warns_and_is_skipped(self, tmp_path):
        good = tmp_path / "src"
        _make_repo(good, "alpha")
        missing = tmp_path / "does_not_exist"

        warnings: list[str] = []
        found = discover_repos(PostupSettings(roots=[str(good), str(missing)]), warnings)

        assert [p.name for p in found] == ["alpha"]
        assert any("does_not_exist" in w for w in warnings)

    def test_no_roots_yields_nothing(self):
        assert discover_repos(PostupSettings(roots=[])) == []
