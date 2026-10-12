from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from dot.hostlinks.manifest import MANIFEST_PATH, HostLink, parse_manifest, read_manifest


class TestManifestPath:
    def test_points_at_buvis_host_links_file(self) -> None:
        assert MANIFEST_PATH == ".config/buvis/host-links"


class TestHostLink:
    def test_construction(self) -> None:
        link = HostLink(target=".zshrc", source=".zshrc.work")

        assert link.target == ".zshrc"
        assert link.source == ".zshrc.work"

    def test_frozen(self) -> None:
        link = HostLink(target=".zshrc", source=".zshrc.work")

        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(link, "target", "other")


class TestParseManifestValid:
    def test_parses_single_entry(self) -> None:
        links, errors = parse_manifest(".zshrc => .zshrc.work\n")

        assert links == [HostLink(".zshrc", ".zshrc.work")]
        assert errors == []

    def test_empty_text_yields_nothing(self) -> None:
        assert parse_manifest("") == ([], [])

    def test_skips_comments_and_blank_lines(self) -> None:
        text = "# header\n\n   \n  # indented comment\n.a => .b\n# a => b\n"

        links, errors = parse_manifest(text)

        assert links == [HostLink(".a", ".b")]
        assert errors == []

    def test_strips_whitespace_around_paths(self) -> None:
        links, errors = parse_manifest("   .a   =>    .b   \n")

        assert links == [HostLink(".a", ".b")]
        assert errors == []

    def test_splits_on_first_arrow_only(self) -> None:
        links, errors = parse_manifest("a => b => c\n")

        assert links == [HostLink("a", "b => c")]
        assert errors == []

    def test_keeps_nested_relative_paths(self) -> None:
        links, errors = parse_manifest(".config/app/conf => .config/app/conf.host\n")

        assert links == [HostLink(".config/app/conf", ".config/app/conf.host")]
        assert errors == []

    def test_preserves_entry_order(self) -> None:
        links, _ = parse_manifest("c => z\na => y\nb => x\n")

        assert [link.target for link in links] == ["c", "a", "b"]


class TestParseManifestErrors:
    def test_reports_missing_arrow(self) -> None:
        links, errors = parse_manifest("just a line\n")

        assert links == []
        assert errors == ["host-links:1: missing '=>'"]

    def test_reports_empty_target(self) -> None:
        links, errors = parse_manifest(" => b\n")

        assert links == []
        assert errors == ["host-links:1: empty path"]

    def test_reports_empty_source(self) -> None:
        links, errors = parse_manifest("a =>   \n")

        assert links == []
        assert errors == ["host-links:1: empty path"]

    @pytest.mark.parametrize("path", ["/etc/x", "~/x", "~", "\\outside", "C:x", "C:\\x", "1:x"])
    def test_reports_absolute_target(self, path: str) -> None:
        links, errors = parse_manifest(f"{path} => b\n")

        assert links == []
        assert errors == ["host-links:1: absolute path"]

    @pytest.mark.parametrize("path", ["/etc/x", "~/x", "\\outside", "C:x", "1:x"])
    def test_reports_absolute_source(self, path: str) -> None:
        links, errors = parse_manifest(f"a => {path}\n")

        assert links == []
        assert errors == ["host-links:1: absolute path"]

    @pytest.mark.parametrize("path", ["../x", "a/../b", "a/..", "a\\..\\b"])
    def test_reports_dotdot_in_target(self, path: str) -> None:
        links, errors = parse_manifest(f"{path} => b\n")

        assert links == []
        assert errors == ["host-links:1: '..' not allowed"]

    @pytest.mark.parametrize("path", ["../x", "a/../b", "a\\..\\b"])
    def test_reports_dotdot_in_source(self, path: str) -> None:
        links, errors = parse_manifest(f"a => {path}\n")

        assert links == []
        assert errors == ["host-links:1: '..' not allowed"]

    def test_allows_dots_inside_names(self) -> None:
        links, errors = parse_manifest("a..b => ..c\n")

        assert links == [HostLink("a..b", "..c")]
        assert errors == []

    def test_reports_target_equals_source(self) -> None:
        links, errors = parse_manifest(".a => .a\n")

        assert links == []
        assert errors == ["host-links:1: target equals source"]

    def test_reports_duplicate_target_and_keeps_first(self) -> None:
        links, errors = parse_manifest(".a => .b\n.a => .c\n")

        assert links == [HostLink(".a", ".b")]
        assert errors == ["host-links:2: duplicate target .a"]

    def test_target_error_wins_over_source_error(self) -> None:
        _, errors = parse_manifest("/abs => ../up\n")

        assert errors == ["host-links:1: absolute path"]

    def test_target_checked_before_source_for_empty(self) -> None:
        _, errors = parse_manifest(" => /abs\n")

        assert errors == ["host-links:1: empty path"]

    def test_path_errors_win_over_equality(self) -> None:
        _, errors = parse_manifest("/x => /x\n")

        assert errors == ["host-links:1: absolute path"]

    def test_invalid_line_does_not_reserve_target(self) -> None:
        links, errors = parse_manifest(".a => /abs\n.a => .b\n")

        assert links == [HostLink(".a", ".b")]
        assert errors == ["host-links:1: absolute path"]


class TestParseManifestMixed:
    def test_reports_each_bad_line_with_own_number_and_keeps_good_ones(self) -> None:
        text = (
            "# comment\n"  # 1
            ".a => .a.host\n"  # 2
            "\n"  # 3
            "no arrow here\n"  # 4
            ".b => ../evil\n"  # 5
            ".c => .c.host\n"  # 6
            ".a => .other\n"  # 7
            "~/x => y\n"  # 8
            ".d => .d\n"  # 9
            ".e => .e.host\n"  # 10
        )

        links, errors = parse_manifest(text)

        assert links == [
            HostLink(".a", ".a.host"),
            HostLink(".c", ".c.host"),
            HostLink(".e", ".e.host"),
        ]
        assert errors == [
            "host-links:4: missing '=>'",
            "host-links:5: '..' not allowed",
            "host-links:7: duplicate target .a",
            "host-links:8: absolute path",
            "host-links:9: target equals source",
        ]


class TestReadManifest:
    def test_reads_entries_from_manifest_file(self, tmp_path: Path) -> None:
        manifest = tmp_path / MANIFEST_PATH
        manifest.parent.mkdir(parents=True)
        manifest.write_text("# hosts\n.a => .a.host\n.b => .b.host\n", encoding="utf-8")

        links, errors = read_manifest(tmp_path)

        assert links == [HostLink(".a", ".a.host"), HostLink(".b", ".b.host")]
        assert errors == []

    def test_returns_parse_errors_from_file(self, tmp_path: Path) -> None:
        manifest = tmp_path / MANIFEST_PATH
        manifest.parent.mkdir(parents=True)
        manifest.write_text(".a => .a.host\nbroken\n", encoding="utf-8")

        links, errors = read_manifest(tmp_path)

        assert links == [HostLink(".a", ".a.host")]
        assert errors == ["host-links:2: missing '=>'"]

    def test_reads_utf8_content(self, tmp_path: Path) -> None:
        manifest = tmp_path / MANIFEST_PATH
        manifest.parent.mkdir(parents=True)
        manifest.write_text("café => café.host\n", encoding="utf-8")

        links, errors = read_manifest(tmp_path)

        assert links == [HostLink("café", "café.host")]
        assert errors == []

    def test_missing_file_returns_empty_without_errors(self, tmp_path: Path) -> None:
        assert read_manifest(tmp_path) == ([], [])

    def test_undecodable_file_reports_single_prefixed_error(self, tmp_path: Path) -> None:
        manifest = tmp_path / MANIFEST_PATH
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes(b"\xff\xfe\x00bad\n")

        links, errors = read_manifest(tmp_path)

        assert links == []
        assert len(errors) == 1
        assert errors[0].startswith("host-links: ")

    def test_unreadable_path_reports_single_prefixed_error(self, tmp_path: Path) -> None:
        (tmp_path / MANIFEST_PATH).mkdir(parents=True)

        links, errors = read_manifest(tmp_path)

        assert links == []
        assert len(errors) == 1
        assert errors[0].startswith("host-links: ")
