from __future__ import annotations

import pytest
from dot.hostfilter import TOKEN, clean, count_home, resolve_home, smudge

HOME = "/Users/bob"
OTHER_HOME = "/home/alice"
WIN_HOME = "C:/Users/bob"


class TestToken:
    def test_token_is_reserved_home_literal(self) -> None:
        assert TOKEN == b"@HOME@"


class TestCleanPosixMatches:
    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (b"/Users/bob/x", b"@HOME@/x"),
            (b'"/Users/bob"', b'"@HOME@"'),
            (b"=/Users/bob", b"=@HOME@"),
            (b"file:///Users/bob", b"file://@HOME@"),
            (b"/Users/bob", b"@HOME@"),
            (b"path /Users/bob\n", b"path @HOME@\n"),
        ],
    )
    def test_replaces_boundary_matched_home(self, data: bytes, expected: bytes) -> None:
        assert clean(data, HOME) == expected

    @pytest.mark.parametrize(
        "data",
        [
            b"/Users/bobby",
            b"/Users/bob.bak",
            b"/Users/bob-old",
            b"/Users/bob_x",
            b"/Users/bob9",
            b"/opt/Users/bob",
            b"x/Users/bob",
            b"./Users/bob",
            b"-/Users/bob",
            b"_/Users/bob",
            b"7/Users/bob",
            b"/Users/bo",
            b"X/Users/bob",
            b"/Users/bobX",
        ],
    )
    def test_leaves_near_miss_without_boundary_untouched(self, data: bytes) -> None:
        assert clean(data, HOME) == data

    def test_boundary_checked_on_both_sides_independently(self) -> None:
        assert clean(b" /Users/bob ", HOME) == b" @HOME@ "
        assert clean(b"a/Users/bob ", HOME) == b"a/Users/bob "
        assert clean(b" /Users/boba", HOME) == b" /Users/boba"
        assert clean(b"Z/Users/bob ", HOME) == b"Z/Users/bob "
        assert clean(b" /Users/bobZ", HOME) == b" /Users/bobZ"

    def test_matches_regex_metacharacters_in_home_literally(self) -> None:
        assert clean(b"/home/axb", "/home/a.b") == b"/home/axb"
        assert clean(b"/home/a.b/x", "/home/a.b") == b"@HOME@/x"
        assert count_home(b"/home/axb /home/a.b", "/home/a.b") == 1

    def test_replaces_every_occurrence_and_skips_near_misses_between(self) -> None:
        data = b"A=/Users/bob/a:/Users/bobby:/Users/bob/b\n'/Users/bob'"

        assert clean(data, HOME) == b"A=@HOME@/a:/Users/bobby:@HOME@/b\n'@HOME@'"

    def test_adjacent_matches_sharing_one_separator_are_both_replaced(self) -> None:
        assert clean(b"/Users/bob:/Users/bob", HOME) == b"@HOME@:@HOME@"
        assert clean(b"/Users/bob /Users/bob /Users/bob", HOME) == b"@HOME@ @HOME@ @HOME@"

    def test_uses_given_home_not_a_fixed_value(self) -> None:
        data = b"/Users/bob/x /home/alice/y"

        assert clean(data, HOME) == b"@HOME@/x /home/alice/y"
        assert clean(data, OTHER_HOME) == b"/Users/bob/x @HOME@/y"

    def test_empty_input_stays_empty(self) -> None:
        assert clean(b"", HOME) == b""

    def test_input_without_home_is_unchanged(self) -> None:
        assert clean(b"nothing to see\n", HOME) == b"nothing to see\n"


class TestCleanBytePreservation:
    def test_preserves_crlf_line_endings(self) -> None:
        data = b"a=/Users/bob/a\r\nb=/Users/bob\r\n"

        assert clean(data, HOME) == b"a=@HOME@/a\r\nb=@HOME@\r\n"

    def test_preserves_utf8_bom(self) -> None:
        data = b"\xef\xbb\xbf/Users/bob/x\n"

        assert clean(data, HOME) == b"\xef\xbb\xbf@HOME@/x\n"

    def test_preserves_non_utf8_bytes_and_treats_them_as_boundaries(self) -> None:
        data = b"\xff\xfe caf\xe9 \xe9/Users/bob\xe9 \x00/Users/bob\x80"

        assert clean(data, HOME) == b"\xff\xfe caf\xe9 \xe9@HOME@\xe9 \x00@HOME@\x80"


class TestCleanReservedToken:
    def test_rejects_input_already_containing_token(self) -> None:
        with pytest.raises(ValueError):
            clean(b"x @HOME@ y", HOME)

    def test_rejects_token_even_when_home_also_present(self) -> None:
        with pytest.raises(ValueError):
            clean(b"/Users/bob/x\n@HOME@/y\n", HOME)

    @pytest.mark.parametrize("data", [b"x=@HOME@", b"a@HOME@b", b"/@HOME@/x", b"@HOME@"])
    def test_rejects_token_regardless_of_preceding_byte(self, data: bytes) -> None:
        with pytest.raises(ValueError):
            clean(data, HOME)

    @pytest.mark.parametrize("data", [b"@HOME", b"HOME@", b"@home@", b"@ HOME@"])
    def test_accepts_partial_or_differently_cased_token(self, data: bytes) -> None:
        assert clean(data, HOME) == data


class TestCleanWindowsSpellings:
    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (b"C:\\Users\\bob\\AppData", b"@HOME@\\AppData"),
            (b'"C:\\\\Users\\\\bob\\\\x"', b'"@HOME@\\\\x"'),
            (b"C:/Users/bob/x", b"@HOME@/x"),
            (b"C:\\Users\\bob", b"@HOME@"),
        ],
    )
    def test_replaces_each_accepted_spelling_and_keeps_suffix_separator(self, data: bytes, expected: bytes) -> None:
        assert clean(data, WIN_HOME) == expected

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (b"c:\\Users\\bob\\x", b"@HOME@\\x"),
            (b"c:\\\\Users\\\\bob", b"@HOME@"),
            (b"c:/Users/bob", b"@HOME@"),
        ],
    )
    def test_matches_drive_letter_case_insensitively(self, data: bytes, expected: bytes) -> None:
        assert clean(data, WIN_HOME) == expected

    def test_matches_uppercase_drive_for_lowercase_home_drive(self) -> None:
        assert clean(b"C:\\Users\\bob\\x", "c:/Users/bob") == b"@HOME@\\x"

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (b"d:\\Users\\bob\\x", b"@HOME@\\x"),
            (b"D:\\\\Users\\\\bob", b"@HOME@"),
            (b"D:/Users/bob/y", b"@HOME@/y"),
            (b"C:\\Users\\bob", b"C:\\Users\\bob"),
        ],
    )
    def test_windows_spellings_apply_to_any_drive_letter(self, data: bytes, expected: bytes) -> None:
        assert clean(data, "D:/Users/bob") == expected

    @pytest.mark.parametrize(
        "data",
        [
            b"C:\\users\\bob",
            b"C:\\Users\\BOB",
            b"C:/users/bob",
            b"C:\\\\USERS\\\\bob",
            b"D:\\Users\\bob",
        ],
    )
    def test_compares_rest_of_path_case_sensitively(self, data: bytes) -> None:
        assert clean(data, WIN_HOME) == data

    @pytest.mark.parametrize(
        "data",
        [b"C:\\Users\\bobby", b"C:/Users/bob.bak", b"C:\\\\Users\\\\bob-old", b"XC:\\Users\\bob"],
    )
    def test_requires_boundaries_for_windows_spellings(self, data: bytes) -> None:
        assert clean(data, WIN_HOME) == data

    def test_counts_all_three_spellings_in_one_input(self) -> None:
        data = b"a=C:\\Users\\bob\nb=C:\\\\Users\\\\bob\nc=C:/Users/bob\nd=C:/Users/bobby\n"

        assert clean(data, WIN_HOME) == b"a=@HOME@\nb=@HOME@\nc=@HOME@\nd=C:/Users/bobby\n"
        assert count_home(data, WIN_HOME) == 3


class TestSmudge:
    def test_replaces_token_with_home(self) -> None:
        assert smudge(b"@HOME@/x", HOME) == b"/Users/bob/x"

    def test_uses_given_home_not_a_fixed_value(self) -> None:
        assert smudge(b"@HOME@/x", OTHER_HOME) == b"/home/alice/x"

    def test_replaces_every_token(self) -> None:
        data = b'a="@HOME@"\r\nb=@HOME@/b:@HOME@\r\n'

        assert smudge(data, HOME) == b'a="/Users/bob"\r\nb=/Users/bob/b:/Users/bob\r\n'

    def test_replaces_token_regardless_of_adjacent_bytes(self) -> None:
        assert smudge(b"x@HOME@y", HOME) == b"x/Users/boby"

    def test_preserves_bytes_outside_tokens(self) -> None:
        data = b"\xef\xbb\xbf\xff@HOME@\xfe\r\n/Users/bobby"

        assert smudge(data, HOME) == b"\xef\xbb\xbf\xff/Users/bob\xfe\r\n/Users/bobby"

    @pytest.mark.parametrize("data", [b"", b"no token here\n", b"@HOME", b"@home@"])
    def test_leaves_token_free_input_untouched(self, data: bytes) -> None:
        assert smudge(data, HOME) == data

    def test_writes_windows_home_with_forward_slashes_and_keeps_suffix(self) -> None:
        data = b"a=@HOME@\\AppData\nb=@HOME@\\\\x\nc=@HOME@/y\n"

        expected = b"a=C:/Users/bob\\AppData\nb=C:/Users/bob\\\\x\nc=C:/Users/bob/y\n"
        assert smudge(data, WIN_HOME) == expected

    def test_writes_backslash_spelled_home_with_forward_slashes(self) -> None:
        assert smudge(b"@HOME@\\x", "C:\\Users\\bob") == b"C:/Users/bob\\x"


class TestCountHome:
    def test_counts_repeated_boundary_matches_only(self) -> None:
        data = b"/Users/bob/a /Users/bobby /Users/bob.bak '/Users/bob' file:///Users/bob"

        assert count_home(data, HOME) == 3

    def test_counts_single_match(self) -> None:
        assert count_home(b"=/Users/bob", HOME) == 1

    def test_returns_zero_for_empty_input(self) -> None:
        assert count_home(b"", HOME) == 0

    def test_returns_zero_for_near_misses_only(self) -> None:
        assert count_home(b"/Users/bobby /opt/Users/bob /Users/bob-old", HOME) == 0

    def test_depends_on_given_home(self) -> None:
        data = b"/home/alice/a /home/alice/b /Users/bob"

        assert count_home(data, OTHER_HOME) == 2
        assert count_home(data, HOME) == 1

    def test_counts_adjacent_matches_sharing_one_separator(self) -> None:
        assert count_home(b"/Users/bob:/Users/bob", HOME) == 2

    def test_matches_number_of_tokens_clean_inserts(self) -> None:
        data = b"x=/Users/bob\r\ny=/Users/bob/z\r\n\xff/Users/bob\xff"

        assert count_home(data, HOME) == clean(data, HOME).count(TOKEN) == 3


POSIX_SAMPLES = [
    b"",
    b"/Users/bob",
    b"/Users/bob/x",
    b'{"path": "/Users/bob/.config", "url": "file:///Users/bob"}\n',
    b"PATH=/Users/bob/bin:/opt/Users/bob:/Users/bobby\r\n",
    b"\xef\xbb\xbfhome=/Users/bob\r\nbak=/Users/bob.bak\r\n",
    b"\xff\xfe\x00/Users/bob\x80 caf\xe9 /Users/bob-old",
    b"no home here",
]


class TestRoundTrips:
    @pytest.mark.parametrize("raw", POSIX_SAMPLES)
    def test_smudge_after_clean_restores_raw_posix_bytes(self, raw: bytes) -> None:
        assert smudge(clean(raw, HOME), HOME) == raw

    @pytest.mark.parametrize("raw", POSIX_SAMPLES)
    def test_clean_after_smudge_restores_cleaned_bytes(self, raw: bytes) -> None:
        cleaned = clean(raw, HOME)

        assert clean(smudge(cleaned, HOME), HOME) == cleaned

    def test_cleaned_bytes_smudge_to_each_hosts_home(self) -> None:
        cleaned = clean(b"src=/Users/bob/src\n", HOME)

        assert smudge(cleaned, OTHER_HOME) == b"src=/home/alice/src\n"
        assert clean(smudge(cleaned, OTHER_HOME), OTHER_HOME) == cleaned


class TestResolveHome:
    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", "/home/carol")
        monkeypatch.setenv("DOTFILES_ROOT", "/srv/dots")
        monkeypatch.delenv("GIT_WORK_TREE", raising=False)

    def test_work_tree_wins_over_dotfiles_root_and_home(self) -> None:
        assert resolve_home("/home/alice", "/tmp/elsewhere") == "/home/alice"

    def test_work_tree_value_reaches_result(self) -> None:
        assert resolve_home("/Users/bob", "/tmp/elsewhere") == "/Users/bob"

    def test_dot_work_tree_resolves_to_cwd(self) -> None:
        assert resolve_home(".", "/home/alice") == "/home/alice"
        assert resolve_home(".", "/Users/bob") == "/Users/bob"

    def test_relative_work_tree_is_made_absolute_against_cwd(self) -> None:
        assert resolve_home("dots", "/home/alice") == "/home/alice/dots"
        assert resolve_home("dots", "/Users/bob") == "/Users/bob/dots"

    def test_strips_trailing_separator_from_work_tree(self) -> None:
        assert resolve_home("/home/alice/", "/tmp") == "/home/alice"

    def test_strips_trailing_separator_from_relative_work_tree(self) -> None:
        assert resolve_home("dots/", "/home/alice") == "/home/alice/dots"

    def test_falls_back_to_dotfiles_root_without_work_tree(self) -> None:
        assert resolve_home(None, "/home/alice") == "/srv/dots"

    def test_dotfiles_root_value_reaches_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", "/opt/other-dots/")

        assert resolve_home(None, "/home/alice") == "/opt/other-dots"

    def test_ignores_git_work_tree_env_and_uses_argument_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GIT_WORK_TREE", "/from/env")

        assert resolve_home(None, "/home/alice") == "/srv/dots"

    def test_falls_back_to_path_home_without_work_tree_or_dotfiles_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT")

        assert resolve_home(None, "/home/alice") == "/home/carol"

    def test_home_fallback_tracks_home_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT")
        monkeypatch.setenv("HOME", "/Users/dave/")

        assert resolve_home(None, "/home/alice") == "/Users/dave"
