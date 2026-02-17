import pytest
from zseq.commands import CommandGetLast


class TestCommandGetLast:
    def test_raises_on_invalid_dir(self, tmp_path):
        with pytest.raises(ValueError, match="is not a directory"):
            CommandGetLast(
                path_dir=str(tmp_path / "nonexistent"),
                is_reporting_misnamed=False,
            )

    def test_finds_max_seq(self, tmp_path):
        (tmp_path / "20240114122450-0010-first.md").touch()
        (tmp_path / "20240114122450-0050-second.md").touch()
        (tmp_path / "20240114122450-0030-third.md").touch()

        cmd = CommandGetLast(path_dir=str(tmp_path), is_reporting_misnamed=False)
        result = cmd.execute()

        assert result.success
        assert "50" in result.output

    def test_no_zettelseq_files(self, tmp_path):
        (tmp_path / "random-file.txt").touch()
        (tmp_path / "another.md").touch()

        cmd = CommandGetLast(path_dir=str(tmp_path), is_reporting_misnamed=False)
        result = cmd.execute()

        assert not result.success
        assert "No files" in result.error

    def test_skips_directories(self, tmp_path):
        (tmp_path / "20240114122450-0010-first.md").touch()
        (tmp_path / "20240114122450-0099-subdir").mkdir()

        cmd = CommandGetLast(path_dir=str(tmp_path), is_reporting_misnamed=False)
        result = cmd.execute()

        assert result.success
        assert "10" in result.output

    def test_empty_dir(self, tmp_path):
        cmd = CommandGetLast(path_dir=str(tmp_path), is_reporting_misnamed=False)
        result = cmd.execute()

        assert not result.success
