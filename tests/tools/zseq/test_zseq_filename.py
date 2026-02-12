from pathlib import Path

import pytest
from zseq.shared import ZseqFilename


class TestIsZettelseq:
    def test_valid_zettelseq(self):
        p = Path("20240114122450-0081-Enhanced-NR.md")
        assert ZseqFilename.is_zettelseq(p) is True

    def test_valid_zettelseq_no_seq(self):
        p = Path("20240114122450.md")
        assert ZseqFilename.is_zettelseq(p) is True

    def test_invalid_zettelseq(self):
        p = Path("not-a-zettelseq.md")
        assert ZseqFilename.is_zettelseq(p) is False

    def test_short_filename(self):
        p = Path("2024.md")
        assert ZseqFilename.is_zettelseq(p) is False

    def test_empty_stem(self):
        p = Path(".md")
        assert ZseqFilename.is_zettelseq(p) is False

    def test_almost_valid_timestamp(self):
        p = Path("20241314122450.md")  # month 13
        assert ZseqFilename.is_zettelseq(p) is False


class TestGetSeqFromZettelseq:
    def test_basic_seq(self):
        assert ZseqFilename.get_seq_from_zettelseq("20240114122450-0081-Enhanced-NR") == 81

    def test_seq_with_leading_zeros(self):
        assert ZseqFilename.get_seq_from_zettelseq("20240114122450-01-note") == 1

    def test_large_seq(self):
        assert ZseqFilename.get_seq_from_zettelseq("20240114122450-9999-big") == 9999

    def test_seq_at_end(self):
        assert ZseqFilename.get_seq_from_zettelseq("20240114122450-42") == 42

    def test_no_seq_raises(self):
        with pytest.raises(ValueError, match="No valid sequence number"):
            ZseqFilename.get_seq_from_zettelseq("20240114122450-abc")

    def test_multi_digit_seq(self):
        assert ZseqFilename.get_seq_from_zettelseq("20240114122450-123-title") == 123
